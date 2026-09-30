"""Reconstruccion de la actividad del cron, sin red ni base de datos.

Los casos salen de lo observado en produccion: GitHub corre los cron
programados con 4 a 6 horas de retraso, y las pruebas locales dejan filas en
job_runs que no deben pasar por ciclos reales.
"""
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import re

import pytest

from src import actividad
from src.ciclos import CICLOS, COT, ciclo_mas_cercano, ciclo_por_cron, siguiente_programado
from src.ejecucion import contexto_de_ejecucion
from src.filters.engine import (
    FilterEngine, MOTIVO_DEPARTAMENTO, MOTIVO_MODALIDAD, MOTIVO_SIN_COINCIDENCIA,
)
from src.notifications.email import EmailNotification, estado_desde_eventos

RAIZ = os.path.join(os.path.dirname(__file__), "..")
DIA = datetime(2026, 9, 29).date()


def cot(hora, minuto=0, dia=DIA):
    return datetime(dia.year, dia.month, dia.day, hora, minuto, tzinfo=COT)


def job(id_, inicio, status="success", **extra):
    return {"id": id_, "started_at": inicio, "completed_at": inicio + timedelta(seconds=30),
            "status": status, "processes_found": 34, "processes_matched": 3,
            "processes_new": 1, "notifications_sent": 1, "notifications_failed": 0,
            "error_message": None, "github_run_id": None, "github_run_url": None,
            "trigger": None, "ciclo": None, "recipient": "c@x.co", "stealth": False,
            "discard_summary": {MOTIVO_SIN_COINCIDENCIA: 31}, **extra}


def run(id_, inicio, estado="completed", conclusion="success", evento="schedule"):
    return {"id": id_, "evento": evento, "estado": estado, "conclusion": conclusion,
            "inicio": inicio, "actualizado": inicio + timedelta(minutes=1),
            "url": f"https://github.com/x/y/actions/runs/{id_}", "numero": id_}


# ==========================================================================
# Ciclos
# ==========================================================================
def test_los_ciclos_coinciden_con_el_workflow():
    """Si alguien cambia el cron en secop.yml, esta prueba lo avisa."""
    with open(os.path.join(RAIZ, ".github", "workflows", "secop.yml"), encoding="utf-8") as f:
        en_workflow = set(re.findall(r"cron:\s*'([^']+)'", f.read()))
    assert en_workflow == {c[3] for c in CICLOS}


def test_ciclo_por_expresion_cron():
    assert ciclo_por_cron("30 18 * * *") == "13:30"
    assert ciclo_por_cron("0 1 * * *") == "20:00"
    assert ciclo_por_cron("* * * * *") is None


def test_ciclo_mas_cercano_para_ejecuciones_sin_cron():
    assert ciclo_mas_cercano(cot(14, 0)) == "13:30"
    assert ciclo_mas_cercano(cot(0, 10)) == "20:00"


def test_siguiente_ciclo_despues_del_ultimo_del_dia():
    assert siguiente_programado(cot(22, 0)) == cot(0, 45, DIA + timedelta(days=1))


def test_contexto_en_github_actions(tmp_path, monkeypatch):
    evento = tmp_path / "evento.json"
    evento.write_text('{"schedule": "0 15 * * *"}', encoding="utf-8")
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.setenv("GITHUB_REPOSITORY", "x/y")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "schedule")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(evento))
    ctx = contexto_de_ejecucion("c@x.co", False, ahora=cot(15, 55))
    assert ctx["ciclo"] == "10:00"
    assert ctx["trigger"] == "schedule"
    assert ctx["github_run_url"] == "https://github.com/x/y/actions/runs/123"


def test_contexto_local(monkeypatch):
    for var in ("GITHUB_RUN_ID", "GITHUB_REPOSITORY", "GITHUB_EVENT_NAME", "GITHUB_EVENT_PATH"):
        monkeypatch.delenv(var, raising=False)
    ctx = contexto_de_ejecucion("c@x.co", True)
    assert ctx["trigger"] == "local"
    assert ctx["github_run_id"] is None


# ==========================================================================
# Unir GitHub con la base y asignar ciclos
# ==========================================================================
def test_las_pruebas_locales_no_ocupan_ciclos():
    ahora = cot(22, 30)
    real = cot(17, 25)
    prueba = cot(21, 54)
    github = {"runs": [run(1, real)]}
    ejecuciones = actividad.unificar([job(10, real), job(11, prueba)], github, ahora)

    origenes = {e["id"]: e["origen"] for e in ejecuciones}
    assert origenes == {10: "programado", 11: "local"}

    ranuras = actividad.asignar_ciclos(ejecuciones, [DIA], ahora)
    de_las_20 = next(r for r in ranuras if r["etiqueta"] == "20:00")
    assert de_las_20["ejecucion"] is None
    assert de_las_20["estado"] == "esperando"


def test_los_retrasos_de_github_se_asignan_en_orden():
    """Observado el 29/09: cada ciclo corrio de 4 a 6 h tarde."""
    ahora = cot(22, 30)
    inicios = [cot(1, 40), cot(6, 33), cot(14, 42), cot(17, 25)]
    github = {"runs": [run(i, t) for i, t in enumerate(inicios)]}
    jobs = [job(100 + i, t) for i, t in enumerate(inicios)]
    ranuras = actividad.asignar_ciclos(actividad.unificar(jobs, github, ahora), [DIA], ahora)

    por_ciclo = {r["etiqueta"]: r for r in ranuras}
    # 01:40 es el ciclo de las 20:00 del dia anterior: no ocupa uno de hoy
    assert por_ciclo["00:45"]["ejecucion"]["id"] == 101
    assert por_ciclo["00:45"]["retraso_min"] == 348
    assert por_ciclo["10:00"]["ejecucion"]["id"] == 102
    assert por_ciclo["13:30"]["ejecucion"]["id"] == 103


def test_un_ciclo_declarado_va_a_su_lugar():
    ahora = cot(22, 30)
    inicio = cot(17, 25)
    jobs = [job(1, inicio, trigger="schedule", ciclo="13:30", github_run_id=9)]
    ranuras = actividad.asignar_ciclos(
        actividad.unificar(jobs, {"runs": [run(9, inicio)]}, ahora), [DIA], ahora)
    assert next(r for r in ranuras if r["etiqueta"] == "13:30")["ejecucion"]["id"] == 1
    assert next(r for r in ranuras if r["etiqueta"] == "10:00")["ejecucion"] is None


def test_un_ciclo_sin_ejecucion_pasa_a_omitido_tras_el_margen():
    ahora = cot(23, 0)
    ranuras = actividad.asignar_ciclos([], [DIA], ahora)
    estados = {r["etiqueta"]: r["estado"] for r in ranuras}
    assert estados["00:45"] == "omitido"      # hace mas de 8 h
    assert estados["20:00"] == "esperando"    # aun dentro del margen


def test_un_run_que_fallo_antes_de_la_base_se_ve_como_fallido():
    ahora = cot(12, 0)
    ejecuciones = actividad.unificar(
        [], {"runs": [run(5, cot(10, 30), conclusion="failure")]}, ahora)
    assert ejecuciones[0]["estado"] == "fallido"
    assert ejecuciones[0]["registrado"] is False


def test_una_ejecucion_que_no_cerro_queda_interrumpida():
    ahora = cot(12, 0)
    colgada = job(1, cot(10, 0), status="running")
    ejecuciones = actividad.unificar([colgada], None, ahora)
    assert ejecuciones[0]["estado"] == "interrumpido"


def test_un_run_en_curso():
    ahora = cot(10, 5)
    en_curso = job(1, cot(10, 4), status="running", github_run_id=3)
    ejecuciones = actividad.unificar(
        [en_curso], {"runs": [run(3, cot(10, 4), estado="in_progress", conclusion=None)]}, ahora)
    assert ejecuciones[0]["estado"] == "en_curso"


# ==========================================================================
# Lo que ve cada rol
# ==========================================================================
def test_el_cliente_no_recibe_campos_tecnicos():
    e = actividad.unificar([job(1, cot(10, 0))], None, cot(12, 0))[0]
    cliente = actividad.publica(e, es_admin=False)
    admin = actividad.publica(e, es_admin=True)
    for campo in ("github_url", "error", "descartes", "origen", "destinatario"):
        assert campo not in cliente
    assert admin["descartes"] == {MOTIVO_SIN_COINCIDENCIA: 31}
    assert cliente["duracion_s"] == 30


def test_eventos_del_cliente_y_del_admin():
    oportunidad = {"id": "P1", "detected_at": cot(10, 1), "name": "Dotacion",
                   "entity_name": "SENA", "city": "Barranquilla", "department": "Atlantico",
                   "base_price": 1, "modality": "Minima", "url": "", "delivery_status": "entregado"}
    omitido = {"estado": "omitido", "fecha": "2026-09-29", "etiqueta": "00:45",
               "programado": cot(0, 45)}
    problema = {"id": 4, "process_id": "P1", "name": "Dotacion",
                "motivo": "Brevo lo reporta como rebotado", "fecha": cot(11, 0)}

    del_cliente = actividad.construir_eventos([oportunidad], [], [omitido], [problema], False)
    del_admin = actividad.construir_eventos([oportunidad], [], [omitido], [problema], True)

    assert [e["tipo"] for e in del_cliente] == ["oportunidad"]
    assert del_cliente[0]["correo"] == "entregado"
    assert {e["tipo"] for e in del_admin} == {"oportunidad", "ciclo_omitido", "correo_problema"}


# ==========================================================================
# Motor: motivo de cada decision
# ==========================================================================
@pytest.fixture()
def motor():
    return FilterEngine({
        "departments": ["Atlantico"], "keywords": ["dotacion"],
        "unspsc_codes": ["V1.53102700"], "certification_keywords": ["pyme"],
        "modalidad_keywords": ["minima cuantia"],
    })


def base(**extra):
    return {"id": "X", "department": "Atlántico", "modality": "Mínima cuantía",
            "name": "", "description": "", "unspsc_code": "", **extra}


def test_motivos_de_coincidencia(motor):
    assert motor.evaluate(base(name="Dotación laboral")) == (True, "palabra clave: dotacion")
    assert motor.evaluate(base(unspsc_code="V1.53102700")) == (True, "código UNSPSC: V1.53102700")
    assert motor.evaluate(base(description="para pyme")) == (True, "atributo especial: pyme")


def test_motivos_de_descarte(motor):
    assert motor.evaluate(base(department="Antioquia")) == (False, MOTIVO_DEPARTAMENTO)
    assert motor.evaluate(base(modality="Licitación")) == (False, MOTIVO_MODALIDAD)
    assert motor.evaluate(base(name="Obra civil")) == (False, MOTIVO_SIN_COINCIDENCIA)


# ==========================================================================
# Correo: identificador de Brevo y estado de entrega
# ==========================================================================
def test_el_envio_guarda_el_message_id_de_brevo():
    respuesta = MagicMock(status_code=201)
    respuesta.json.return_value = {"messageId": "<abc@smtp-relay.mailin.fr>"}
    with patch("src.notifications.email.httpx.Client") as cliente:
        cliente.return_value.__enter__ = lambda s: s
        cliente.return_value.__exit__ = MagicMock(return_value=False)
        cliente.return_value.post.return_value = respuesta
        with patch("src.notifications.email.BREVO_API_KEY", "k"):
            emailer = EmailNotification()
            assert emailer.send({"id": "P1", "name": "x"}, "c@x.co") == (True, None)
    assert emailer.last_message_id == "<abc@smtp-relay.mailin.fr>"


def test_estado_de_entrega_toma_el_peor_desenlace():
    assert estado_desde_eventos({"requests", "delivered"}) == "entregado"
    assert estado_desde_eventos({"requests", "delivered", "opened"}) == "abierto"
    assert estado_desde_eventos({"requests", "hardBounces"}) == "rebotado"
    assert estado_desde_eventos({"requests", "deferred"}) == "diferido"
    assert estado_desde_eventos(set()) == "enviado"


# ==========================================================================
# Motor completo, con base, SECOP y Brevo simulados
# ==========================================================================
def test_el_motor_registra_la_trazabilidad_de_cada_ciclo():
    import src.main as motor

    procesos = [
        base(id="P1", name="Dotación textil"),
        base(id="P2", name="Obra civil"),
        base(id="P3", department="Antioquia", name="Dotación"),
    ]
    config = {"email": "c@x.co", "departments": ["Atlantico"], "keywords": ["dotacion"],
              "unspsc_codes": [], "certification_keywords": [],
              "modalidad_keywords": ["minima cuantia"]}
    emailer = MagicMock()
    emailer.send.return_value = (True, None)
    emailer.last_message_id = "<m1>"

    with patch.object(motor, "get_connection"), patch.object(motor, "init_db"), \
         patch.object(motor, "load_config", return_value=config), \
         patch.object(motor, "SecopDataSource") as fuente, \
         patch.object(motor, "EmailNotification", return_value=emailer), \
         patch.object(motor, "STEALTH_MODE", False), \
         patch.object(motor, "time"), \
         patch.object(motor, "start_job_run", return_value=7) as abrir, \
         patch.object(motor, "save_process", return_value=True), \
         patch.object(motor, "record_run_match") as anotar, \
         patch.object(motor, "mark_notified") as notificado, \
         patch.object(motor, "complete_job_run") as cerrar, \
         patch.object(motor, "actualizar_entregas") as entregas:
        fuente.return_value.fetch_processes.return_value = procesos
        motor.main()

    assert abrir.call_args.args[1]["recipient"] == "c@x.co"
    anotar.assert_called_once()
    assert anotar.call_args.args[1:] == (7, "P1", True, "palabra clave: dotacion")
    assert notificado.call_args.kwargs == {"job_run_id": 7, "message_id": "<m1>"}
    resumen = cerrar.call_args.kwargs
    assert resumen["processes_found"] == 3
    assert resumen["processes_matched"] == 1
    assert resumen["processes_new"] == 1
    assert resumen["notifications_sent"] == 1
    assert resumen["discard_summary"].adapted == {
        MOTIVO_SIN_COINCIDENCIA: 1, MOTIVO_DEPARTAMENTO: 1}
    entregas.assert_called_once()
