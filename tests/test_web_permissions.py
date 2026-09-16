"""Control de acceso por rol del servidor web.

Estas pruebas levantan el servidor real en un puerto libre y hablan con el por
HTTP, para verificar lo que importa: que el backend RECHAZA la peticion cuando
el rol no autoriza, sin depender de que el frontend haya ocultado el boton.
"""
import json
import shutil
import socketserver
import threading
from http.client import HTTPConnection

import pytest

from src import web_server


# ==========================================================================
# Infraestructura de pruebas
# ==========================================================================
@pytest.fixture()
def usuarios_temporales(tmp_path, monkeypatch):
    """Copia users.json a un temporal para no mutar el archivo del repo."""
    destino = tmp_path / "users.json"
    shutil.copy(web_server.USERS_PATH, destino)
    monkeypatch.setattr(web_server, "USERS_PATH", str(destino))
    return destino


@pytest.fixture()
def config_temporal(tmp_path, monkeypatch):
    """Copia client_config.json para que los POST no toquen el archivo real."""
    destino = tmp_path / "client_config.json"
    shutil.copy(web_server.CONFIG_PATH, destino)
    monkeypatch.setattr(web_server, "CONFIG_PATH", str(destino))
    return destino


@pytest.fixture()
def notificaciones_temporales(tmp_path, monkeypatch):
    """Copia notifications.json para no mutar el archivo del repo."""
    destino = tmp_path / "notifications.json"
    shutil.copy(web_server.NOTIFICATIONS_PATH, destino)
    monkeypatch.setattr(web_server, "NOTIFICATIONS_PATH", str(destino))
    return destino


@pytest.fixture()
def servidor(usuarios_temporales, config_temporal, notificaciones_temporales):
    """Servidor real en un puerto efimero, apagado al terminar la prueba."""
    web_server.SESSIONS.clear()
    httpd = socketserver.TCPServer(("127.0.0.1", 0), web_server.SecopMonitorHandler)
    hilo = threading.Thread(target=httpd.serve_forever, daemon=True)
    hilo.start()
    yield httpd.server_address[1]
    httpd.shutdown()
    httpd.server_close()
    web_server.SESSIONS.clear()


class Cliente:
    """Cliente HTTP minimo que conserva la cookie de sesion."""

    def __init__(self, puerto):
        self.puerto = puerto
        self.cookie = None

    def peticion(self, metodo, ruta, cuerpo=None):
        conn = HTTPConnection("127.0.0.1", self.puerto, timeout=10)
        cabeceras = {"Content-Type": "application/json"}
        if self.cookie:
            cabeceras["Cookie"] = self.cookie
        datos = json.dumps(cuerpo or {}) if metodo in ("POST", "PUT") else None
        conn.request(metodo, ruta, body=datos, headers=cabeceras)
        resp = conn.getresponse()
        crudo = resp.read().decode("utf-8")
        set_cookie = resp.getheader("Set-Cookie")
        if set_cookie:
            self.cookie = set_cookie.split(";")[0]
        conn.close()
        try:
            return resp.status, json.loads(crudo)
        except json.JSONDecodeError:
            return resp.status, crudo

    def entrar(self, rol, correo=None):
        cuerpo = {"rol": rol}
        if correo:
            cuerpo["correo"] = correo
        return self.peticion("POST", "/api/auth/login", cuerpo)


@pytest.fixture()
def anonimo(servidor):
    return Cliente(servidor)


@pytest.fixture()
def cliente_usuario(servidor):
    c = Cliente(servidor)
    estado, _ = c.entrar("usuario")
    assert estado == 200
    return c


@pytest.fixture()
def cliente_admin(servidor):
    c = Cliente(servidor)
    estado, _ = c.entrar("admin")
    assert estado == 200
    return c


# ==========================================================================
# Mapa de permisos
# ==========================================================================
def test_usuario_no_tiene_permisos_de_escritura():
    assert not web_server.puede("usuario", "editar_configuracion")
    assert not web_server.puede("usuario", "editar_metricas")
    assert not web_server.puede("usuario", "gestionar_usuarios")
    assert not web_server.puede("usuario", "ver_monitoreo")


def test_usuario_tiene_sus_permisos_de_lectura():
    assert web_server.puede("usuario", "ver_metricas")
    assert web_server.puede("usuario", "ver_arquitectura")
    assert web_server.puede("usuario", "ver_notificaciones")


def test_admin_hereda_todo_lo_del_usuario():
    assert web_server.PERMISOS_USUARIO <= web_server.PERMISOS_ADMIN


def test_rol_desconocido_no_puede_nada():
    assert not web_server.puede("superadmin", "ver_metricas")
    assert not web_server.puede("", "ver_metricas")
    assert not web_server.puede(None, "ver_metricas")


# ==========================================================================
# Autenticacion
# ==========================================================================
def test_login_con_rol_invalido_es_rechazado(anonimo):
    estado, cuerpo = anonimo.entrar("superadmin")
    assert estado == 400
    assert cuerpo["codigo"] == "rol_invalido"


def test_login_de_usuario_devuelve_sus_permisos(anonimo):
    estado, cuerpo = anonimo.entrar("usuario")
    assert estado == 200
    assert cuerpo["usuario"]["rol"] == "usuario"
    assert "ver_metricas" in cuerpo["permisos"]
    assert "editar_configuracion" not in cuerpo["permisos"]


def test_login_de_admin_incluye_permisos_de_escritura(anonimo):
    estado, cuerpo = anonimo.entrar("admin")
    assert estado == 200
    assert cuerpo["usuario"]["rol"] == "admin"
    assert "editar_configuracion" in cuerpo["permisos"]
    assert "gestionar_usuarios" in cuerpo["permisos"]


def test_cuenta_inactiva_no_puede_entrar(anonimo):
    # u-004 (Supervisora Regional) esta marcada como inactiva en users.json
    estado, cuerpo = anonimo.entrar("admin", correo="supervisora@secopmonitor.co")
    assert estado == 403
    assert cuerpo["codigo"] == "cuenta_inactiva"


def test_login_con_rol_que_no_corresponde_al_usuario(anonimo):
    estado, cuerpo = anonimo.entrar("admin", correo="cliente@secopmonitor.co")
    assert estado == 403
    assert cuerpo["codigo"] == "rol_no_corresponde"


def test_sin_sesion_no_hay_identidad(anonimo):
    estado, cuerpo = anonimo.peticion("GET", "/api/auth/me")
    assert estado == 401
    assert cuerpo["codigo"] == "sin_sesion"


def test_la_sesion_se_conserva_entre_peticiones(cliente_usuario):
    estado, cuerpo = cliente_usuario.peticion("GET", "/api/auth/me")
    assert estado == 200
    assert cuerpo["usuario"]["rol"] == "usuario"


def test_cerrar_sesion_invalida_la_cookie(cliente_admin):
    estado, _ = cliente_admin.peticion("POST", "/api/auth/logout")
    assert estado == 200
    estado, cuerpo = cliente_admin.peticion("GET", "/api/auth/me")
    assert estado == 401
    assert cuerpo["codigo"] == "sin_sesion"


def test_el_login_registra_el_acceso(anonimo, usuarios_temporales):
    anonimo.entrar("usuario")
    usuarios = json.loads(usuarios_temporales.read_text(encoding="utf-8"))["usuarios"]
    cliente = next(u for u in usuarios if u["id"] == "u-002")
    assert cliente["accesos"] == 1
    assert cliente["ultimo_acceso"] is not None


# ==========================================================================
# Endpoints protegidos
# ==========================================================================
def test_guardar_configuracion_exige_sesion(anonimo):
    estado, cuerpo = anonimo.peticion("POST", "/api/config", {"name": "X"})
    assert estado == 401
    assert cuerpo["codigo"] == "sin_sesion"


def test_usuario_no_puede_guardar_configuracion(cliente_usuario, config_temporal):
    antes = config_temporal.read_text(encoding="utf-8")
    estado, cuerpo = cliente_usuario.peticion("POST", "/api/config", {"name": "Pirata"})
    assert estado == 403
    assert cuerpo["codigo"] == "sin_permiso"
    # Y sobre todo: el archivo no cambio.
    assert config_temporal.read_text(encoding="utf-8") == antes


def test_admin_si_puede_guardar_configuracion(cliente_admin, config_temporal):
    estado, cuerpo = cliente_admin.peticion(
        "POST", "/api/config", {"name": "Cliente de prueba", "keywords": []})
    assert estado == 200
    assert cuerpo["status"] == "ok"
    guardado = json.loads(config_temporal.read_text(encoding="utf-8"))
    assert guardado["name"] == "Cliente de prueba"


def test_usuario_no_puede_probar_filtros(cliente_usuario):
    estado, cuerpo = cliente_usuario.peticion(
        "POST", "/api/filter/test", {"name": "dotacion textil"})
    assert estado == 403
    assert cuerpo["codigo"] == "sin_permiso"


def test_usuario_no_puede_ver_el_monitoreo_en_vivo(cliente_usuario):
    estado, cuerpo = cliente_usuario.peticion("GET", "/api/secop/live")
    assert estado == 403
    assert cuerpo["permiso"] == "ver_monitoreo"


def test_usuario_si_puede_leer_el_perfil_del_cliente(cliente_usuario):
    estado, cuerpo = cliente_usuario.peticion("GET", "/api/config")
    assert estado == 200
    assert "keywords" in cuerpo


def test_leer_el_perfil_exige_sesion(anonimo):
    estado, _ = anonimo.peticion("GET", "/api/config")
    assert estado == 401


# ==========================================================================
# Metricas y sincronizacion manual (Fase 3)
# ==========================================================================
@pytest.fixture()
def sin_red(monkeypatch):
    """Evita salir a internet: sustituye la consulta real por datos fijos."""
    procesos = [
        {"is_matched": True, "certifications": {"favorece_pyme": True}},
        {"is_matched": True, "certifications": {"favorece_pyme": False}},
        {"is_matched": False, "certifications": {"favorece_pyme": False}},
    ]
    monkeypatch.setattr(
        web_server.SecopMonitorHandler, "_consultar_procesos",
        lambda self: procesos)
    return procesos


def test_las_metricas_exigen_sesion(anonimo):
    estado, cuerpo = anonimo.peticion("GET", "/api/metrics")
    assert estado == 401
    assert cuerpo["codigo"] == "sin_sesion"


def test_el_usuario_si_puede_leer_las_metricas(cliente_usuario, sin_red):
    estado, cuerpo = cliente_usuario.peticion("GET", "/api/metrics")
    assert estado == 200
    assert cuerpo["analizados"] == 3
    assert cuerpo["coincidencias"] == 2
    assert cuerpo["con_ventaja"] == 1


def test_las_metricas_no_exponen_la_lista_de_procesos(cliente_usuario, sin_red):
    """El usuario ve los numeros, no los procesos: esa es la diferencia
    entre ver_metricas y ver_monitoreo."""
    _, cuerpo = cliente_usuario.peticion("GET", "/api/metrics")
    assert set(cuerpo) == {
        "analizados", "coincidencias", "notificados", "con_ventaja", "actualizado"}


def test_el_usuario_no_puede_lanzar_la_sincronizacion(cliente_usuario, sin_red):
    estado, cuerpo = cliente_usuario.peticion("POST", "/api/sync")
    assert estado == 403
    assert cuerpo["permiso"] == "editar_metricas"


def test_el_admin_si_puede_lanzar_la_sincronizacion(cliente_admin, sin_red):
    estado, cuerpo = cliente_admin.peticion("POST", "/api/sync")
    assert estado == 200
    assert cuerpo["procesos"] == 3


def test_la_sincronizacion_cuenta_como_accion_del_usuario(
        cliente_admin, sin_red, usuarios_temporales):
    cliente_admin.peticion("POST", "/api/sync")
    usuarios = json.loads(usuarios_temporales.read_text(encoding="utf-8"))["usuarios"]
    admin = next(u for u in usuarios if u["id"] == "u-001")
    assert admin["acciones"] == 1


def test_la_sincronizacion_sin_sesion_es_rechazada(anonimo):
    estado, _ = anonimo.peticion("POST", "/api/sync")
    assert estado == 401


# ==========================================================================
# Notificaciones (Fase 4) — disponibles para los dos roles
# ==========================================================================
def test_las_notificaciones_exigen_sesion(anonimo):
    estado, cuerpo = anonimo.peticion("GET", "/api/notifications")
    assert estado == 401
    assert cuerpo["codigo"] == "sin_sesion"


def test_el_usuario_puede_ver_sus_notificaciones(cliente_usuario):
    estado, cuerpo = cliente_usuario.peticion("GET", "/api/notifications")
    assert estado == 200
    assert len(cuerpo["notificaciones"]) == 4
    assert cuerpo["sin_leer"] == 2


def test_el_admin_tambien_puede_verlas(cliente_admin):
    estado, cuerpo = cliente_admin.peticion("GET", "/api/notifications")
    assert estado == 200
    assert cuerpo["sin_leer"] == 2


def test_marcar_una_notificacion_como_leida(cliente_usuario):
    estado, cuerpo = cliente_usuario.peticion(
        "POST", "/api/notifications/read", {"id": "n-004"})
    assert estado == 200
    assert cuerpo["sin_leer"] == 1

    _, lista = cliente_usuario.peticion("GET", "/api/notifications")
    marcada = next(n for n in lista["notificaciones"] if n["id"] == "n-004")
    assert marcada["leida"] is True


def test_marcar_todas_como_leidas(cliente_usuario):
    estado, cuerpo = cliente_usuario.peticion("POST", "/api/notifications/read")
    assert estado == 200
    assert cuerpo["sin_leer"] == 0


def test_marcar_una_notificacion_inexistente(cliente_usuario):
    estado, cuerpo = cliente_usuario.peticion(
        "POST", "/api/notifications/read", {"id": "n-999"})
    assert estado == 404
    assert cuerpo["codigo"] == "no_encontrada"


def test_marcar_sin_sesion_es_rechazado(anonimo, notificaciones_temporales):
    antes = notificaciones_temporales.read_text(encoding="utf-8")
    estado, _ = anonimo.peticion("POST", "/api/notifications/read")
    assert estado == 401
    assert notificaciones_temporales.read_text(encoding="utf-8") == antes


# ==========================================================================
# Gestion de usuarios (Fase 5) — solo admin
# ==========================================================================
def test_listar_usuarios_exige_sesion(anonimo):
    estado, cuerpo = anonimo.peticion("GET", "/api/users")
    assert estado == 401
    assert cuerpo["codigo"] == "sin_sesion"


def test_el_usuario_no_puede_listar_usuarios(cliente_usuario):
    estado, cuerpo = cliente_usuario.peticion("GET", "/api/users")
    assert estado == 403
    assert cuerpo["permiso"] == "gestionar_usuarios"


def test_el_admin_lista_usuarios_con_metricas_agregadas(cliente_admin):
    estado, cuerpo = cliente_admin.peticion("GET", "/api/users")
    assert estado == 200
    assert len(cuerpo["usuarios"]) == 4
    assert cuerpo["resumen"]["total"] == 4
    assert cuerpo["resumen"]["activos"] == 3
    assert cuerpo["resumen"]["inactivos"] == 1
    assert cuerpo["resumen"]["administradores"] == 2


def test_el_usuario_no_puede_crear_usuarios(cliente_usuario, usuarios_temporales):
    antes = usuarios_temporales.read_text(encoding="utf-8")
    estado, _ = cliente_usuario.peticion("POST", "/api/users", {
        "nombre": "Intruso", "correo": "intruso@x.co", "rol": "admin"})
    assert estado == 403
    assert usuarios_temporales.read_text(encoding="utf-8") == antes


def test_el_admin_crea_un_usuario(cliente_admin):
    estado, cuerpo = cliente_admin.peticion("POST", "/api/users", {
        "nombre": "Nueva Analista", "correo": "nueva@secopmonitor.co",
        "rol": "usuario", "estado": "activo"})
    assert estado == 201
    assert cuerpo["usuario"]["id"] == "u-005"
    assert cuerpo["usuario"]["accesos"] == 0


def test_no_se_admiten_correos_duplicados(cliente_admin):
    estado, cuerpo = cliente_admin.peticion("POST", "/api/users", {
        "nombre": "Duplicado", "correo": "admin@secopmonitor.co", "rol": "usuario"})
    assert estado == 400
    assert cuerpo["codigo"] == "datos_invalidos"


def test_no_se_admite_un_rol_inventado(cliente_admin):
    estado, cuerpo = cliente_admin.peticion("POST", "/api/users", {
        "nombre": "Raro", "correo": "raro@secopmonitor.co", "rol": "superadmin"})
    assert estado == 400
    assert "rol" in cuerpo["error"].lower()


def test_el_admin_cambia_el_rol_de_otro_usuario(cliente_admin):
    estado, cuerpo = cliente_admin.peticion(
        "PUT", "/api/users/u-003", {"rol": "admin"})
    assert estado == 200
    assert cuerpo["usuario"]["rol"] == "admin"


def test_el_admin_desactiva_a_otro_usuario(cliente_admin):
    estado, cuerpo = cliente_admin.peticion(
        "PUT", "/api/users/u-002", {"estado": "inactivo"})
    assert estado == 200
    assert cuerpo["usuario"]["estado"] == "inactivo"


def test_un_admin_no_puede_desactivarse_a_si_mismo(cliente_admin):
    """Salvaguarda: quien administra no puede dejarse fuera del sistema."""
    estado, cuerpo = cliente_admin.peticion(
        "PUT", "/api/users/u-001", {"estado": "inactivo"})
    assert estado == 409
    assert cuerpo["codigo"] == "autobloqueo"


def test_un_admin_no_puede_degradarse_a_si_mismo(cliente_admin):
    estado, cuerpo = cliente_admin.peticion(
        "PUT", "/api/users/u-001", {"rol": "usuario"})
    assert estado == 409
    assert cuerpo["codigo"] == "autobloqueo"


def test_un_admin_no_puede_eliminarse_a_si_mismo(cliente_admin):
    estado, cuerpo = cliente_admin.peticion("DELETE", "/api/users/u-001")
    assert estado == 409
    assert cuerpo["codigo"] == "autobloqueo"


def test_el_admin_elimina_a_otro_usuario(cliente_admin):
    estado, cuerpo = cliente_admin.peticion("DELETE", "/api/users/u-003")
    assert estado == 200
    assert cuerpo["eliminado"] == "u-003"

    _, lista = cliente_admin.peticion("GET", "/api/users")
    assert all(u["id"] != "u-003" for u in lista["usuarios"])


def test_el_usuario_no_puede_eliminar(cliente_usuario, usuarios_temporales):
    antes = usuarios_temporales.read_text(encoding="utf-8")
    estado, _ = cliente_usuario.peticion("DELETE", "/api/users/u-003")
    assert estado == 403
    assert usuarios_temporales.read_text(encoding="utf-8") == antes


def test_editar_un_usuario_inexistente(cliente_admin):
    estado, cuerpo = cliente_admin.peticion(
        "PUT", "/api/users/u-999", {"nombre": "Fantasma"})
    assert estado == 404
    assert cuerpo["codigo"] == "no_encontrado"


def test_gestionar_usuarios_cuenta_como_accion(cliente_admin, usuarios_temporales):
    cliente_admin.peticion("POST", "/api/users", {
        "nombre": "Contable", "correo": "contable@secopmonitor.co", "rol": "usuario"})
    usuarios = json.loads(usuarios_temporales.read_text(encoding="utf-8"))["usuarios"]
    admin = next(u for u in usuarios if u["id"] == "u-001")
    assert admin["acciones"] == 1


def test_un_usuario_creado_inactivo_no_puede_entrar(cliente_admin, servidor):
    cliente_admin.peticion("POST", "/api/users", {
        "nombre": "Pendiente", "correo": "pendiente@secopmonitor.co",
        "rol": "usuario", "estado": "inactivo"})
    otro = Cliente(servidor)
    estado, cuerpo = otro.entrar("usuario", correo="pendiente@secopmonitor.co")
    assert estado == 403
    assert cuerpo["codigo"] == "cuenta_inactiva"
