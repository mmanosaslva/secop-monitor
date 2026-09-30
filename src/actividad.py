"""Actividad del monitor: que hizo el cron, reconstruido para la web.

Dos fuentes, cada una con su verdad:

- GitHub Actions dice CUANDO corrio el workflow y como termino.
- La base de datos (job_runs, run_matches, notifications) dice QUE HIZO.

La web solo lee. Lo unico que escribe es que eventos ya vio cada usuario
(notification_reads), que no afecta al motor.

El modulo separa la logica pura (unificar, asignar ciclos, armar eventos),
que se prueba sin red ni base de datos, de las funciones que consultan.
"""
import json
import os
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Optional

from src.ciclos import COT, MARGEN_RETRASO, programados_del_dia, siguiente_programado

GITHUB_REPO = os.environ.get("GITHUB_REPO", "mmanosaslva/secop-monitor")
GITHUB_WORKFLOW = os.environ.get("GITHUB_WORKFLOW_FILE", "secop.yml")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

# GitHub retrasa los cron programados varias horas en la capa gratuita
# (observado: 4 a 6 h). Un run se asocia al ciclo pendiente mas antiguo dentro
# de esta ventana.
VENTANA_ASIGNACION = timedelta(hours=10)
# Una ejecucion que sigue 'running' pasado este tiempo murio sin cerrar.
LIMITE_EN_CURSO = timedelta(hours=1)
# Tolerancia para enlazar filas antiguas de job_runs con su run de GitHub.
HOLGURA_ENLACE = timedelta(minutes=3)

ENTREGAS_PROBLEMA = {"rebotado", "bloqueado", "spam"}


# ==========================================================================
# GitHub Actions (lectura publica, con cache)
# ==========================================================================
_cache: Dict[str, tuple] = {}
CACHE_SEGUNDOS = 120


def _github(ruta: str):
    """GET a la API de GitHub. None si falla: la vista sigue con la base."""
    ahora = time.time()
    guardado = _cache.get(ruta)
    if guardado and ahora - guardado[0] < CACHE_SEGUNDOS:
        return guardado[1]
    cabeceras = {"Accept": "application/vnd.github+json", "User-Agent": "secop-monitor"}
    if GITHUB_TOKEN:
        cabeceras["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    try:
        req = urllib.request.Request(f"https://api.github.com{ruta}", headers=cabeceras)
        with urllib.request.urlopen(req, timeout=8) as resp:
            datos = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return guardado[1] if guardado else None
    _cache[ruta] = (ahora, datos)
    return datos


def _fecha_iso(valor: Optional[str]) -> Optional[datetime]:
    if not valor:
        return None
    return datetime.fromisoformat(valor.replace("Z", "+00:00"))


def consultar_github(dias: int) -> Optional[dict]:
    """Estado del workflow y sus runs recientes, ya normalizados."""
    base = f"/repos/{GITHUB_REPO}/actions/workflows/{GITHUB_WORKFLOW}"
    flujo = _github(base)
    desde = (datetime.now(timezone.utc) - timedelta(days=dias)).date().isoformat()
    runs = _github(f"{base}/runs?per_page=100&created=%3E%3D{desde}")
    if flujo is None or runs is None:
        return None
    return {
        "estado_workflow": flujo.get("state"),
        "url_workflow": f"https://github.com/{GITHUB_REPO}/actions/workflows/{GITHUB_WORKFLOW}",
        "runs": [
            {
                "id": r["id"],
                "evento": r.get("event"),
                "estado": r.get("status"),
                "conclusion": r.get("conclusion"),
                "inicio": _fecha_iso(r.get("run_started_at") or r.get("created_at")),
                "actualizado": _fecha_iso(r.get("updated_at")),
                "url": r.get("html_url"),
                "numero": r.get("run_number"),
            }
            for r in runs.get("workflow_runs", [])
        ],
    }


# ==========================================================================
# Logica pura
# ==========================================================================
def _origen(trigger: Optional[str], evento_github: Optional[str]) -> str:
    evento = evento_github or trigger
    if evento == "schedule":
        return "programado"
    if evento == "workflow_dispatch":
        return "manual"
    return "local"


def unificar(job_runs: List[dict], github: Optional[dict], ahora: datetime) -> List[dict]:
    """Une cada run de GitHub con la fila de job_runs que produjo.

    Filas nuevas: por github_run_id. Filas anteriores a la trazabilidad: por
    hora, si la fila empezo mientras el run estaba activo. Las filas sin run
    de GitHub son ejecuciones locales (pruebas, desarrollo).
    """
    por_id = {j["github_run_id"]: j for j in job_runs if j.get("github_run_id")}
    usados = set()
    ejecuciones = []

    for run in (github or {}).get("runs", []):
        job = por_id.get(run["id"])
        if job is None and run["inicio"]:
            fin = (run["actualizado"] or ahora) + HOLGURA_ENLACE
            job = next(
                (j for j in job_runs
                 if j["id"] not in usados and not j.get("github_run_id")
                 and run["inicio"] - HOLGURA_ENLACE <= j["started_at"] <= fin),
                None,
            )
        if job is not None:
            usados.add(job["id"])
        ejecuciones.append(_ejecucion(job, run, ahora))

    for job in job_runs:
        if job["id"] in usados:
            continue
        # Sin datos de GitHub no se puede distinguir una fila antigua del cron
        # de una prueba local: se trata como programada para no ocultar nada.
        if github is None and not job.get("trigger"):
            ejecuciones.append(_ejecucion(job, None, ahora, origen="programado"))
        else:
            ejecuciones.append(_ejecucion(job, None, ahora))

    ejecuciones.sort(key=lambda e: e["inicio"] or ahora, reverse=True)
    return ejecuciones


def _ejecucion(job: Optional[dict], run: Optional[dict], ahora: datetime,
               origen: Optional[str] = None) -> dict:
    inicio = (job or {}).get("started_at") or (run or {}).get("inicio")
    fin = (job or {}).get("completed_at")
    if fin is None and run and run.get("estado") == "completed":
        fin = run.get("actualizado")

    return {
        "id": job["id"] if job else None,
        "github_run_id": run["id"] if run else (job or {}).get("github_run_id"),
        "github_url": run["url"] if run else (job or {}).get("github_run_url"),
        "origen": origen or _origen((job or {}).get("trigger"), (run or {}).get("evento")),
        "ciclo_declarado": (job or {}).get("ciclo") if (job or {}).get("trigger") == "schedule" else None,
        "estado": _estado(job, run, ahora),
        "inicio": inicio,
        "fin": fin,
        "analizados": (job or {}).get("processes_found"),
        "coincidencias": (job or {}).get("processes_matched"),
        "nuevos": (job or {}).get("processes_new"),
        "enviados": (job or {}).get("notifications_sent"),
        "fallidos": (job or {}).get("notifications_failed"),
        "silencioso": (job or {}).get("stealth"),
        "destinatario": (job or {}).get("recipient"),
        "descartes": (job or {}).get("discard_summary") or {},
        "error": (job or {}).get("error_message"),
        "registrado": job is not None,
    }


def _estado(job: Optional[dict], run: Optional[dict], ahora: datetime) -> str:
    if job is None:
        if run is None:
            return "desconocido"
        if run["estado"] in ("queued", "waiting", "requested", "pending"):
            return "en_cola"
        if run["estado"] == "in_progress":
            return "en_curso"
        # Termino sin dejar fila: fallo antes de llegar a la base (dependencias,
        # secretos, conexion). El detalle esta en el log de GitHub.
        return "completado" if run.get("conclusion") == "success" else "fallido"

    if job["status"] == "success":
        return "completado"
    if job["status"] == "failed":
        return "fallido"
    # 'running'
    if run is not None and run["estado"] == "completed":
        return "interrumpido"
    if ahora - job["started_at"] > LIMITE_EN_CURSO:
        return "interrumpido"
    return "en_curso"


def asignar_ciclos(ejecuciones: List[dict], dias: List, ahora: datetime) -> List[dict]:
    """Cada ciclo programado de `dias` con la ejecucion que lo cubrio.

    Una ejecucion que declara su ciclo va a ese. Las demas programadas
    (filas antiguas) ocupan, en orden, el ciclo pendiente mas antiguo: GitHub
    las encola en orden aunque las retrase.
    """
    ranuras = []
    for dia in sorted(dias):
        for p in programados_del_dia(dia):
            ranuras.append({**p, "fecha": dia.isoformat(), "ejecucion": None})
    # Ciclos del dia anterior al rango: absorben runs retrasados que no son
    # de este rango (el de las 20:00 que corre de madrugada).
    previas = [
        {**p, "fecha": None, "ejecucion": None}
        for p in programados_del_dia(min(dias) - timedelta(days=1))
    ] if dias else []
    todas = previas + ranuras

    programadas = sorted(
        (e for e in ejecuciones if e["origen"] == "programado" and e["inicio"]),
        key=lambda e: e["inicio"],
    )
    for e in programadas:
        if e["ciclo_declarado"]:
            candidatas = [r for r in todas if r["etiqueta"] == e["ciclo_declarado"]
                          and r["programado"] <= e["inicio"] + timedelta(minutes=15)]
            destino = max(candidatas, key=lambda r: r["programado"]) if candidatas else None
            if destino is not None and destino["ejecucion"] is None:
                destino["ejecucion"] = e
            continue
        for r in todas:
            if (r["ejecucion"] is None
                    and r["programado"] <= e["inicio"] + timedelta(minutes=15)
                    and e["inicio"] - r["programado"] <= VENTANA_ASIGNACION):
                r["ejecucion"] = e
                break

    for r in ranuras:
        e = r["ejecucion"]
        if e is not None:
            r["estado"] = e["estado"]
            retraso = (e["inicio"] - r["programado"]).total_seconds()
            r["retraso_min"] = max(0, int(retraso // 60))
        elif ahora < r["programado"]:
            r["estado"] = "programado"
        elif ahora < r["programado"] + MARGEN_RETRASO:
            r["estado"] = "esperando"
        else:
            r["estado"] = "omitido"
    return ranuras


def construir_eventos(oportunidades: List[dict], ejecuciones: List[dict],
                      ranuras: List[dict], correos_problema: List[dict],
                      es_admin: bool) -> List[dict]:
    """Eventos de la campana. El cliente ve oportunidades; el admin, ademas,
    todo lo que indique que algo no funciono."""
    eventos = []
    for o in oportunidades:
        eventos.append({
            "id": f"op:{o['id']}",
            "tipo": "oportunidad",
            "fecha": o["detected_at"],
            "titulo": o["name"],
            "entidad": o["entity_name"],
            "ubicacion": ", ".join(x for x in (o.get("city"), o.get("department")) if x),
            "valor_base": o.get("base_price"),
            "modalidad": o.get("modality"),
            "url": o.get("url"),
            "proceso_id": o["id"],
            "correo": o.get("delivery_status") or ("fallido" if o.get("email_status") == "failed" else None),
        })
    if es_admin:
        for e in ejecuciones:
            if e["estado"] in ("fallido", "interrumpido") and e["origen"] != "local":
                eventos.append({
                    "id": f"fallo:{e['github_run_id'] or e['id']}",
                    "tipo": "ciclo_fallido",
                    "fecha": e["inicio"],
                    "titulo": "Una ejecución del cron falló" if e["estado"] == "fallido"
                              else "Una ejecución del cron quedó sin terminar",
                    "detalle": e.get("error") or "Revisa el log en GitHub.",
                    "url": e.get("github_url"),
                })
        for r in ranuras:
            if r["estado"] == "omitido":
                eventos.append({
                    "id": f"omitido:{r['fecha']}:{r['etiqueta']}",
                    "tipo": "ciclo_omitido",
                    "fecha": r["programado"] + MARGEN_RETRASO,
                    "titulo": f"El ciclo de las {r['etiqueta']} no se ejecutó",
                    "detalle": f"GitHub no lo corrió en las {int(MARGEN_RETRASO.total_seconds() // 3600)} h siguientes.",
                })
        for c in correos_problema:
            eventos.append({
                "id": f"correo:{c['id']}",
                "tipo": "correo_problema",
                "fecha": c["fecha"],
                "titulo": "Un correo no llegó al cliente",
                "detalle": f"{c['name']} · {c['motivo']}",
                "proceso_id": c["process_id"],
            })
    eventos.sort(key=lambda ev: ev["fecha"], reverse=True)
    return eventos


def dias_recientes(ahora: datetime, cantidad: int) -> List:
    hoy = ahora.astimezone(COT).date()
    return [hoy - timedelta(days=i) for i in range(cantidad)]


# ==========================================================================
# Serializacion para la API
# ==========================================================================
CAMPOS_TECNICOS = ("github_url", "error", "descartes", "silencioso", "origen",
                   "github_run_id", "registrado")


def publica(ejecucion: Optional[dict], es_admin: bool) -> Optional[dict]:
    """Proyeccion de una ejecucion: el cliente no ve logs ni descartes."""
    if ejecucion is None:
        return None
    datos = {k: _json(v) for k, v in ejecucion.items() if k != "ciclo_declarado"}
    if ejecucion.get("inicio") and ejecucion.get("fin"):
        datos["duracion_s"] = int((ejecucion["fin"] - ejecucion["inicio"]).total_seconds())
    if not es_admin:
        for campo in CAMPOS_TECNICOS:
            datos.pop(campo, None)
        datos.pop("destinatario", None)
    return datos


def _json(valor):
    if isinstance(valor, datetime):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return float(valor)
    return valor


def serializar(obj):
    """Convierte datetimes y Decimals en estructuras anidadas."""
    if isinstance(obj, dict):
        return {k: serializar(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [serializar(v) for v in obj]
    return _json(obj)


# ==========================================================================
# Consultas a la base de datos del motor (solo lectura, salvo leidos)
# ==========================================================================
def _filas(conn, sql: str, params=()) -> List[dict]:
    cursor = conn.cursor()
    try:
        cursor.execute(sql, params)
        columnas = [d[0] for d in cursor.description]
        return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    finally:
        cursor.close()


def leer_job_runs(conn, desde: datetime) -> List[dict]:
    return _filas(conn, """
        SELECT id, started_at, completed_at, status, processes_found, processes_matched,
               processes_new, notifications_sent, notifications_failed, error_message,
               github_run_id, github_run_url, trigger, ciclo, recipient, stealth,
               discard_summary
        FROM job_runs WHERE started_at >= %s ORDER BY started_at DESC
    """, (desde,))


def leer_coincidencias(conn, job: dict) -> List[dict]:
    """Procesos que coincidieron en una ejecucion, con el estado de su correo.

    Las ejecuciones anteriores a run_matches solo guardaron los procesos
    nuevos: se recuperan por la hora en que se detectaron.
    """
    columnas = """
        p.id, p.name, p.entity_name, p.department, p.city, p.base_price, p.modality,
        p.url, p.deadline, p.favorece_mujer_lider, p.favorece_pyme,
        p.requiere_equidad_genero, n.status AS email_status, n.delivery_status,
        n.sent_at
    """
    ultimo_correo = """
        LEFT JOIN LATERAL (
            SELECT status, delivery_status, sent_at FROM notifications
            WHERE process_id = p.id ORDER BY created_at DESC LIMIT 1
        ) n ON TRUE
    """
    filas = _filas(conn, f"""
        SELECT {columnas}, m.is_new, m.match_reason
        FROM run_matches m JOIN processes p ON p.id = m.process_id {ultimo_correo}
        WHERE m.job_run_id = %s ORDER BY m.is_new DESC, p.base_price DESC NULLS LAST
    """, (job["id"],))
    if filas or job.get("trigger"):
        return filas
    fin = job.get("completed_at") or (job["started_at"] + LIMITE_EN_CURSO)
    return _filas(conn, f"""
        SELECT {columnas}, TRUE AS is_new, NULL AS match_reason
        FROM processes p {ultimo_correo}
        WHERE p.detected_at BETWEEN %s AND %s ORDER BY p.base_price DESC NULLS LAST
    """, (job["started_at"], fin))


def leer_oportunidades(conn, desde: datetime) -> List[dict]:
    return _filas(conn, """
        SELECT p.id, p.name, p.entity_name, p.city, p.department, p.base_price,
               p.modality, p.url, p.detected_at, n.status AS email_status,
               n.delivery_status
        FROM processes p
        LEFT JOIN LATERAL (
            SELECT status, delivery_status FROM notifications
            WHERE process_id = p.id ORDER BY created_at DESC LIMIT 1
        ) n ON TRUE
        WHERE p.detected_at >= %s ORDER BY p.detected_at DESC LIMIT 60
    """, (desde,))


def leer_correos_problema(conn, desde: datetime) -> List[dict]:
    filas = _filas(conn, """
        SELECT n.id, n.process_id, p.name, n.status, n.delivery_status, n.error_message,
               COALESCE(n.delivery_updated_at, n.created_at) AS fecha
        FROM notifications n JOIN processes p ON p.id = n.process_id
        WHERE n.created_at >= %s
          AND (n.status = 'failed' OR n.delivery_status = ANY(%s))
    """, (desde, list(ENTREGAS_PROBLEMA)))
    for f in filas:
        f["motivo"] = ("no se pudo enviar" if f["status"] == "failed"
                       else f"Brevo lo reporta como {f['delivery_status']}")
    return filas


def leer_leidos(conn, user_id: str) -> set:
    return {f["event_key"] for f in _filas(
        conn, "SELECT event_key FROM notification_reads WHERE user_id = %s", (user_id,))}


def marcar_leidos(conn, user_id: str, claves: List[str]) -> None:
    cursor = conn.cursor()
    try:
        for clave in claves:
            cursor.execute("""
                INSERT INTO notification_reads (user_id, event_key) VALUES (%s, %s)
                ON CONFLICT DO NOTHING
            """, (user_id, clave))
        conn.commit()
    finally:
        cursor.close()


def leer_totales(conn, desde: datetime) -> dict:
    fila = _filas(conn, """
        SELECT
          (SELECT COUNT(*) FROM processes WHERE detected_at >= %s) AS nuevas,
          (SELECT COUNT(*) FROM processes WHERE detected_at >= %s AND
             (favorece_mujer_lider OR favorece_pyme OR requiere_equidad_genero)) AS con_ventaja,
          (SELECT COUNT(*) FROM notifications WHERE status = 'sent' AND sent_at >= %s) AS enviados,
          (SELECT COUNT(*) FROM notifications WHERE created_at >= %s AND
             (status = 'failed' OR delivery_status = ANY(%s))) AS con_problema
    """, (desde, desde, desde, desde, list(ENTREGAS_PROBLEMA)))
    return fila[0]


# ==========================================================================
# Vistas completas que sirve la API
# ==========================================================================
DIAS_HISTORIAL = 7


def reconstruir(conn, ahora: datetime, dias: int = DIAS_HISTORIAL):
    """Ejecuciones unificadas y ciclos de los ultimos `dias` dias."""
    fechas = dias_recientes(ahora, dias)
    desde = datetime.combine(min(fechas) - timedelta(days=1), datetime.min.time(), COT)
    github = consultar_github(dias + 1)
    ejecuciones = unificar(leer_job_runs(conn, desde), github, ahora)
    ranuras = asignar_ciclos(ejecuciones, fechas, ahora)
    return github, ejecuciones, ranuras


def panel(conn, ahora: datetime, es_admin: bool) -> dict:
    github, ejecuciones, ranuras = reconstruir(conn, ahora)
    hoy = ahora.astimezone(COT).date().isoformat()

    visibles = [e for e in ejecuciones if es_admin or e["origen"] != "local"]
    # Lo que corrio el cron, no una prueba local.
    ultima = next((e for e in ejecuciones if e["origen"] != "local" and e["registrado"]
                   and e["estado"] in ("completado", "fallido")), None)

    def ranura_publica(r):
        return {
            "fecha": r["fecha"], "etiqueta": r["etiqueta"], "nombre": r["nombre"],
            "programado": r["programado"].isoformat(), "estado": r["estado"],
            "retraso_min": r.get("retraso_min"),
            "ejecucion": publica(r["ejecucion"], es_admin),
        }

    respuesta = {
        "ahora": ahora.isoformat(),
        "hoy": [ranura_publica(r) for r in ranuras if r["fecha"] == hoy],
        "historial": [ranura_publica(r) for r in ranuras if r["fecha"] != hoy],
        "ultima": publica(ultima, es_admin),
        "siguiente": siguiente_programado(ahora).isoformat(),
        "github_disponible": github is not None,
        "workflow_activo": (github or {}).get("estado_workflow") in (None, "active"),
    }
    if es_admin:
        respuesta["ejecuciones"] = [publica(e, True) for e in visibles[:40]]
        respuesta["estado_workflow"] = (github or {}).get("estado_workflow")
        respuesta["url_workflow"] = (github or {}).get("url_workflow")
    return respuesta


def detalle(conn, job_id: int, es_admin: bool) -> Optional[dict]:
    filas = _filas(conn, """
        SELECT id, started_at, completed_at, status, processes_found, processes_matched,
               processes_new, notifications_sent, notifications_failed, error_message,
               github_run_id, github_run_url, trigger, ciclo, recipient, stealth,
               discard_summary
        FROM job_runs WHERE id = %s
    """, (job_id,))
    if not filas:
        return None
    job = filas[0]
    ahora = datetime.now(timezone.utc)
    # Se une con GitHub igual que en el panel: asi las filas anteriores a la
    # trazabilidad tambien enlazan su log y se distinguen de las locales.
    dias = max(1, (ahora - job["started_at"]).days + 2)
    ejecucion = next((e for e in unificar([job], consultar_github(dias), ahora)
                      if e["id"] == job["id"]), _ejecucion(job, None, ahora))
    coincidencias = leer_coincidencias(conn, job)
    return serializar({
        "ejecucion": publica(ejecucion, es_admin),
        # Antes de run_matches solo se guardaban contadores: de esas
        # ejecuciones se conocen los procesos nuevos, no todos los que coincidieron.
        "detalle_completo": bool(job.get("trigger")),
        "coincidencias": [
            {**c, "certificaciones": {
                "favorece_mujer_lider": c.pop("favorece_mujer_lider"),
                "favorece_pyme": c.pop("favorece_pyme"),
                "requiere_equidad_genero": c.pop("requiere_equidad_genero"),
            }}
            for c in coincidencias
        ],
    })


def eventos_de(conn, ahora: datetime, es_admin: bool, user_id: str) -> List[dict]:
    desde = ahora - timedelta(days=14)
    ejecuciones, ranuras, problemas = [], [], []
    if es_admin:
        _, ejecuciones, ranuras = reconstruir(conn, ahora, dias=2)
        problemas = leer_correos_problema(conn, desde)
    eventos = construir_eventos(leer_oportunidades(conn, desde), ejecuciones,
                                ranuras, problemas, es_admin)
    leidos = leer_leidos(conn, user_id)
    for ev in eventos:
        ev["leida"] = ev["id"] in leidos
    return serializar(eventos[:40])


def metricas(conn, ahora: datetime) -> dict:
    _, ejecuciones, _ = reconstruir(conn, ahora, dias=2)
    ultima = next((e for e in ejecuciones if e["origen"] != "local"
                   and e["estado"] == "completado" and e["registrado"]), None)
    totales = leer_totales(conn, ahora - timedelta(days=7))
    return serializar({
        "analizados": (ultima or {}).get("analizados") or 0,
        "coincidencias": (ultima or {}).get("coincidencias") or 0,
        "notificados": totales["enviados"],
        "nuevas": totales["nuevas"],
        "con_ventaja": totales["con_ventaja"],
        "correos_con_problema": totales["con_problema"],
        "ultimo_ciclo": (ultima or {}).get("inicio"),
        "actualizado": ahora,
    })
