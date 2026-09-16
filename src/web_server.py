import http.server
import socketserver
import json
import os
import secrets
import sys
import urllib.parse
from datetime import datetime, timezone
from http.cookies import SimpleCookie
from typing import Dict, Optional

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Safe imports for dependencies that might be missing in local system python
try:
    from src.sources.secop import SecopDataSource
    from src.filters.engine import FilterEngine, load_config
    from src.config import SECOP_APP_TOKEN
    HAS_BACKEND_DEPS = True
except ModuleNotFoundError as e:
    HAS_BACKEND_DEPS = False
    print(f"[SECOP WebServer Warning] Dependencias locales no instaladas completamente ({e}). Usando modo interactivo directo.")


PORT = int(os.environ.get("PORT", 8080))
WEB_DIR = os.path.join(os.path.dirname(__file__), "web")
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config", "client_config.json")
USERS_PATH = os.path.join(PROJECT_ROOT, "config", "users.json")
NOTIFICATIONS_PATH = os.path.join(PROJECT_ROOT, "config", "notifications.json")

COOKIE_NAME = "secop_sid"

# ==========================================================================
# Roles y permisos — única fuente de verdad del backend.
# El frontend replica este mapa en app.js (funcion puede()), pero la decision
# que vale es esta: el render puede ocultar, solo el backend autoriza.
# ==========================================================================
PERMISOS_USUARIO = {
    "ver_metricas",
    "ver_arquitectura",
    "ver_notificaciones",
    "ver_perfil_cliente",
}

PERMISOS_ADMIN = PERMISOS_USUARIO | {
    "editar_metricas",
    "ver_monitoreo",
    "editar_configuracion",
    "gestionar_usuarios",
    "probar_filtros",
}

PERMISOS: Dict[str, set] = {
    "usuario": PERMISOS_USUARIO,
    "admin": PERMISOS_ADMIN,
}

# token de sesion -> {"user_id": str, "rol": str}
SESSIONS: Dict[str, dict] = {}


def ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def puede(rol: str, permiso: str) -> bool:
    """Resuelve un permiso para un rol. Un rol desconocido no puede nada."""
    return permiso in PERMISOS.get(rol, set())


def leer_usuarios() -> list:
    with open(USERS_PATH, "r", encoding="utf-8") as f:
        return json.load(f).get("usuarios", [])


def guardar_usuarios(usuarios: list) -> None:
    with open(USERS_PATH, "w", encoding="utf-8") as f:
        json.dump({"usuarios": usuarios}, f, ensure_ascii=False, indent=2)


def buscar_usuario(user_id: str) -> Optional[dict]:
    return next((u for u in leer_usuarios() if u["id"] == user_id), None)


def usuario_publico(usuario: dict) -> dict:
    """Proyeccion del usuario que se expone al navegador."""
    return {
        "id": usuario["id"],
        "nombre": usuario["nombre"],
        "correo": usuario["correo"],
        "rol": usuario["rol"],
        "estado": usuario["estado"],
        "ultimo_acceso": usuario.get("ultimo_acceso"),
        "accesos": usuario.get("accesos", 0),
        "acciones": usuario.get("acciones", 0),
    }


def leer_notificaciones() -> list:
    with open(NOTIFICATIONS_PATH, "r", encoding="utf-8") as f:
        return json.load(f).get("notificaciones", [])


def guardar_notificaciones(notificaciones: list) -> None:
    with open(NOTIFICATIONS_PATH, "w", encoding="utf-8") as f:
        json.dump({"notificaciones": notificaciones}, f, ensure_ascii=False, indent=2)


def registrar_accion(user_id: str) -> None:
    """Suma una accion al usuario, para las metricas agregadas de uso."""
    usuarios = leer_usuarios()
    for u in usuarios:
        if u["id"] == user_id:
            u["acciones"] = u.get("acciones", 0) + 1
            guardar_usuarios(usuarios)
            return


class SecopMonitorHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def log_message(self, format, *args):
        # Clean logging format
        print(f"[SECOP WebServer] {self.address_string()} - {format % args}")

    def send_json_response(self, data: dict, status: int = 200, cookie: str = None):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        if cookie:
            self.send_header('Set-Cookie', cookie)
        self.end_headers()
        self.wfile.write(body)

    # ----------------------------------------------------------------------
    # Sesion y control de acceso
    # ----------------------------------------------------------------------
    def sesion_actual(self) -> Optional[dict]:
        raw = self.headers.get('Cookie')
        if not raw:
            return None
        cookie = SimpleCookie()
        try:
            cookie.load(raw)
        except Exception:
            return None
        morsel = cookie.get(COOKIE_NAME)
        if not morsel:
            return None
        return SESSIONS.get(morsel.value)

    def exigir(self, permiso: str) -> Optional[dict]:
        """Devuelve la sesion si el rol autoriza; si no, responde y devuelve None.

        401 cuando no hay sesion, 403 cuando la sesion existe pero el rol no
        alcanza. El llamador debe cortar en cuanto reciba None.
        """
        sesion = self.sesion_actual()
        if sesion is None:
            self.send_json_response(
                {"error": "No hay sesion activa", "codigo": "sin_sesion"}, 401)
            return None
        if not puede(sesion["rol"], permiso):
            self.send_json_response({
                "error": "Tu rol no autoriza esta accion",
                "codigo": "sin_permiso",
                "permiso": permiso,
                "rol": sesion["rol"],
            }, 403)
            return None
        return sesion

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.end_headers()

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path

        if path == "/api/auth/me":
            self.handle_auth_me()
        elif path == "/api/stats":
            self.handle_get_stats()
        elif path == "/api/config":
            self.handle_get_config()
        elif path == "/api/secop/live":
            self.handle_live_secop()
        elif path == "/api/metrics":
            self.handle_get_metrics()
        elif path == "/api/notifications":
            self.handle_get_notifications()
        elif path == "/api/users":
            self.handle_list_users()
        else:
            # Fallback to serving static SPA files
            super().do_GET()

    def _leer_payload(self) -> dict:
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b'{}'
        try:
            return json.loads(post_data.decode('utf-8'))
        except Exception:
            return {}

    def do_POST(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        payload = self._leer_payload()

        if path == "/api/auth/login":
            self.handle_login(payload)
        elif path == "/api/auth/logout":
            self.handle_logout()
        elif path == "/api/filter/test":
            self.handle_test_filter(payload)
        elif path == "/api/config":
            self.handle_save_config(payload)
        elif path == "/api/sync":
            self.handle_manual_sync()
        elif path == "/api/notifications/read":
            self.handle_mark_notification(payload)
        elif path == "/api/users":
            self.handle_create_user(payload)
        else:
            self.send_json_response({"error": "Endpoint not found"}, 404)

    def do_PUT(self):
        path = urllib.parse.urlparse(self.path).path
        payload = self._leer_payload()
        if path.startswith("/api/users/"):
            self.handle_update_user(path.rsplit("/", 1)[-1], payload)
        else:
            self.send_json_response({"error": "Endpoint not found"}, 404)

    def do_DELETE(self):
        path = urllib.parse.urlparse(self.path).path
        if path.startswith("/api/users/"):
            self.handle_delete_user(path.rsplit("/", 1)[-1])
        else:
            self.send_json_response({"error": "Endpoint not found"}, 404)

    # ----------------------------------------------------------------------
    # Gestion de usuarios (solo admin)
    # ----------------------------------------------------------------------
    def handle_list_users(self):
        if self.exigir("gestionar_usuarios") is None:
            return
        usuarios = leer_usuarios()
        activos = [u for u in usuarios if u["estado"] == "activo"]
        self.send_json_response({
            "usuarios": [usuario_publico(u) for u in usuarios],
            "resumen": {
                "total": len(usuarios),
                "activos": len(activos),
                "inactivos": len(usuarios) - len(activos),
                "administradores": sum(1 for u in usuarios if u["rol"] == "admin"),
                "accesos": sum(u.get("accesos", 0) for u in usuarios),
                "acciones": sum(u.get("acciones", 0) for u in usuarios),
            },
        })

    def _validar_usuario(self, datos: dict, usuarios: list, id_actual=None):
        """Devuelve un mensaje de error, o None si los datos son validos."""
        nombre = (datos.get("nombre") or "").strip()
        correo = (datos.get("correo") or "").strip().lower()
        rol = datos.get("rol")
        estado = datos.get("estado", "activo")

        if not nombre:
            return "El nombre es obligatorio"
        if not correo or "@" not in correo:
            return "El correo no es valido"
        if rol not in PERMISOS:
            return "El rol debe ser admin o usuario"
        if estado not in ("activo", "inactivo"):
            return "El estado debe ser activo o inactivo"
        if any(u["correo"].lower() == correo and u["id"] != id_actual for u in usuarios):
            return "Ya existe un usuario con ese correo"
        return None

    def handle_create_user(self, payload: dict):
        sesion = self.exigir("gestionar_usuarios")
        if sesion is None:
            return

        usuarios = leer_usuarios()
        error = self._validar_usuario(payload, usuarios)
        if error:
            self.send_json_response(
                {"error": error, "codigo": "datos_invalidos"}, 400)
            return

        numeros = [int(u["id"].split("-")[1]) for u in usuarios if u["id"].startswith("u-")]
        nuevo = {
            "id": f"u-{max(numeros, default=0) + 1:03d}",
            "nombre": payload["nombre"].strip(),
            "correo": payload["correo"].strip().lower(),
            "rol": payload["rol"],
            "estado": payload.get("estado", "activo"),
            "ultimo_acceso": None,
            "accesos": 0,
            "acciones": 0,
        }
        usuarios.append(nuevo)
        guardar_usuarios(usuarios)
        registrar_accion(sesion["user_id"])
        self.send_json_response({"usuario": usuario_publico(nuevo)}, 201)

    def handle_update_user(self, user_id: str, payload: dict):
        sesion = self.exigir("gestionar_usuarios")
        if sesion is None:
            return

        usuarios = leer_usuarios()
        actual = next((u for u in usuarios if u["id"] == user_id), None)
        if actual is None:
            self.send_json_response(
                {"error": "No existe ese usuario", "codigo": "no_encontrado"}, 404)
            return

        datos = {
            "nombre": payload.get("nombre", actual["nombre"]),
            "correo": payload.get("correo", actual["correo"]),
            "rol": payload.get("rol", actual["rol"]),
            "estado": payload.get("estado", actual["estado"]),
        }
        error = self._validar_usuario(datos, usuarios, id_actual=user_id)
        if error:
            self.send_json_response(
                {"error": error, "codigo": "datos_invalidos"}, 400)
            return

        # Salvaguardas: nadie se deja a si mismo fuera, y el sistema nunca se
        # queda sin un administrador activo que pueda volver a entrar.
        propio = user_id == sesion["user_id"]
        if propio and (datos["rol"] != actual["rol"] or datos["estado"] != "activo"):
            self.send_json_response(
                {"error": "No puedes cambiar tu propio rol ni desactivar tu cuenta",
                 "codigo": "autobloqueo"}, 409)
            return

        pierde_admin = (actual["rol"] == "admin" and actual["estado"] == "activo"
                        and (datos["rol"] != "admin" or datos["estado"] != "activo"))
        if pierde_admin and self._admins_activos(usuarios) <= 1:
            self.send_json_response(
                {"error": "Debe quedar al menos un administrador activo",
                 "codigo": "ultimo_admin"}, 409)
            return

        actual.update({
            "nombre": datos["nombre"].strip(),
            "correo": datos["correo"].strip().lower(),
            "rol": datos["rol"],
            "estado": datos["estado"],
        })
        guardar_usuarios(usuarios)
        registrar_accion(sesion["user_id"])
        self.send_json_response({"usuario": usuario_publico(actual)})

    def handle_delete_user(self, user_id: str):
        sesion = self.exigir("gestionar_usuarios")
        if sesion is None:
            return

        usuarios = leer_usuarios()
        objetivo = next((u for u in usuarios if u["id"] == user_id), None)
        if objetivo is None:
            self.send_json_response(
                {"error": "No existe ese usuario", "codigo": "no_encontrado"}, 404)
            return
        if user_id == sesion["user_id"]:
            self.send_json_response(
                {"error": "No puedes eliminar tu propia cuenta",
                 "codigo": "autobloqueo"}, 409)
            return
        if (objetivo["rol"] == "admin" and objetivo["estado"] == "activo"
                and self._admins_activos(usuarios) <= 1):
            self.send_json_response(
                {"error": "Debe quedar al menos un administrador activo",
                 "codigo": "ultimo_admin"}, 409)
            return

        guardar_usuarios([u for u in usuarios if u["id"] != user_id])
        registrar_accion(sesion["user_id"])
        self.send_json_response({"status": "ok", "eliminado": user_id})

    @staticmethod
    def _admins_activos(usuarios: list) -> int:
        return sum(1 for u in usuarios
                   if u["rol"] == "admin" and u["estado"] == "activo")

    # ----------------------------------------------------------------------
    # Autenticacion
    # ----------------------------------------------------------------------
    def handle_login(self, payload: dict):
        rol = payload.get("rol")
        if rol not in PERMISOS:
            self.send_json_response(
                {"error": "Rol invalido", "codigo": "rol_invalido"}, 400)
            return

        usuarios = leer_usuarios()
        correo = (payload.get("correo") or "").strip().lower()
        if correo:
            elegido = next(
                (u for u in usuarios if u["correo"].lower() == correo), None)
            if elegido is None:
                self.send_json_response(
                    {"error": "No existe un usuario con ese correo",
                     "codigo": "usuario_no_encontrado"}, 404)
                return
            if elegido["rol"] != rol:
                self.send_json_response(
                    {"error": "El usuario no tiene ese rol",
                     "codigo": "rol_no_corresponde"}, 403)
                return
        else:
            # Sin correo: entra el primer usuario activo del rol pedido.
            elegido = next(
                (u for u in usuarios
                 if u["rol"] == rol and u["estado"] == "activo"), None)
            if elegido is None:
                self.send_json_response(
                    {"error": "No hay usuarios activos con ese rol",
                     "codigo": "sin_usuarios"}, 404)
                return

        if elegido["estado"] != "activo":
            self.send_json_response(
                {"error": "La cuenta esta inactiva", "codigo": "cuenta_inactiva"}, 403)
            return

        # Registrar el acceso
        for u in usuarios:
            if u["id"] == elegido["id"]:
                u["ultimo_acceso"] = ahora_iso()
                u["accesos"] = u.get("accesos", 0) + 1
                elegido = u
                break
        guardar_usuarios(usuarios)

        token = secrets.token_urlsafe(32)
        SESSIONS[token] = {"user_id": elegido["id"], "rol": elegido["rol"]}

        cookie = f"{COOKIE_NAME}={token}; Path=/; HttpOnly; SameSite=Strict"
        self.send_json_response({
            "usuario": usuario_publico(elegido),
            "permisos": sorted(PERMISOS[elegido["rol"]]),
        }, 200, cookie=cookie)

    def handle_logout(self):
        raw = self.headers.get('Cookie')
        if raw:
            cookie = SimpleCookie()
            try:
                cookie.load(raw)
                morsel = cookie.get(COOKIE_NAME)
                if morsel:
                    SESSIONS.pop(morsel.value, None)
            except Exception:
                pass
        expirada = f"{COOKIE_NAME}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"
        self.send_json_response({"status": "ok"}, 200, cookie=expirada)

    def handle_auth_me(self):
        sesion = self.sesion_actual()
        if sesion is None:
            self.send_json_response(
                {"error": "No hay sesion activa", "codigo": "sin_sesion"}, 401)
            return
        usuario = buscar_usuario(sesion["user_id"])
        if usuario is None or usuario["estado"] != "activo":
            self.send_json_response(
                {"error": "La cuenta ya no esta disponible",
                 "codigo": "cuenta_inactiva"}, 401)
            return
        self.send_json_response({
            "usuario": usuario_publico(usuario),
            "permisos": sorted(PERMISOS[usuario["rol"]]),
        })

    # ----------------------------------------------------------------------
    # Datos SECOP
    # ----------------------------------------------------------------------
    def handle_live_secop(self):
        if self.exigir("ver_monitoreo") is None:
            return
        try:
            self.send_json_response(self._consultar_procesos())
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)

    def _consultar_procesos(self) -> list:
        """Trae los procesos de SECOP II y los pasa por el motor de filtros."""
        if HAS_BACKEND_DEPS:
            config = load_config(CONFIG_PATH)
            source = SecopDataSource(app_token=SECOP_APP_TOKEN)
            departments = config.get("departments", [])
            raw_processes = source.fetch_processes(
                departments=departments, modality="Mínima cuantía", max_results=50)

            engine = FilterEngine(config)
            results = []
            for p in raw_processes:
                p["is_matched"] = engine.matches(p)
                p["certifications"] = engine.detect_certifications(p)
                results.append(p)
            return results

        # Standard library fetch directly from datos.gov.co API
        import urllib.request
        config = self._read_config_file()
        depts = ",".join(f"'{d}'" for d in config.get("departments", ["Atlantico", "Bolivar"]))
        url = f"https://www.datos.gov.co/resource/p6dx-8zbt.json?$where=departamento_entidad%20IN%20({urllib.parse.quote(depts)})%20AND%20estado_del_procedimiento='Publicado'&amp;$limit=30"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            raw_data = json.loads(response.read().decode('utf-8'))

        results = []
        for r in raw_data:
            texto = (r.get("nombre_del_procedimiento", "") + r.get("descripci_n_del_procedimiento", "")).lower()
            results.append({
                "id": r.get("id_del_proceso", "CO1.REQ.000"),
                "entity_name": r.get("entidad", ""),
                "department": r.get("departamento_entidad", ""),
                "city": r.get("ciudad_entidad", ""),
                "name": r.get("nombre_del_procedimiento", ""),
                "description": r.get("descripci_n_del_procedimiento", ""),
                "modality": r.get("modalidad_de_contratacion", "Mínima cuantía"),
                "base_price": float(r.get("precio_base", 0) or 0),
                "unspsc_code": r.get("codigo_principal_de_categoria", ""),
                "url": r.get("urlproceso", {}).get("url", "") if isinstance(r.get("urlproceso"), dict) else str(r.get("urlproceso", "")),
                "is_matched": True,
                "certifications": {
                    "favorece_mujer_lider": "mujer" in texto,
                    "favorece_pyme": "pyme" in texto,
                    "requiere_equidad_genero": "genero" in texto,
                }
            })
        return results

    def _read_config_file(self):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    def handle_get_config(self):
        if self.exigir("ver_perfil_cliente") is None:
            return
        try:
            config = self._read_config_file()
            self.send_json_response(config)
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)

    def handle_save_config(self, payload: dict):
        sesion = self.exigir("editar_configuracion")
        if sesion is None:
            return
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            registrar_accion(sesion["user_id"])
            self.send_json_response({"status": "ok", "message": "Configuración guardada en client_config.json"})
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)

    def handle_test_filter(self, payload: dict):
        sesion = self.exigir("probar_filtros")
        if sesion is None:
            return
        try:
            if HAS_BACKEND_DEPS:
                config = load_config(CONFIG_PATH)
                engine = FilterEngine(config)
                is_matched = engine.matches(payload)
                certs = engine.detect_certifications(payload)
            else:
                config = self._read_config_file()
                text = (payload.get("name", "") + " " + payload.get("description", "")).lower()
                is_matched = any(kw.lower() in text for kw in config.get("keywords", []))
                certs = {
                    "favorece_mujer_lider": "mujer" in text,
                    "favorece_pyme": "pyme" in text,
                    "requiere_equidad_genero": "genero" in text
                }
            self.send_json_response({
                "is_matched": is_matched,
                "certifications": certs,
                "process": payload
            })
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)

    def handle_get_metrics(self):
        """KPIs agregados del panel.

        El rol usuario necesita los NUMEROS del panel de metricas pero no la
        lista de procesos: por eso este endpoint devuelve solo conteos y exige
        ver_metricas, mientras /api/secop/live exige ver_monitoreo.
        """
        if self.exigir("ver_metricas") is None:
            return
        try:
            procesos = self._consultar_procesos()
        except Exception as e:
            self.send_json_response(
                {"error": f"No se pudo consultar SECOP II: {e}",
                 "codigo": "fuente_no_disponible"}, 503)
            return

        coincidencias = [p for p in procesos if p.get("is_matched")]
        con_ventaja = [
            p for p in procesos
            if any((p.get("certifications") or {}).values())
        ]
        self.send_json_response({
            "analizados": len(procesos),
            "coincidencias": len(coincidencias),
            "notificados": len(coincidencias),
            "con_ventaja": len(con_ventaja),
            "actualizado": ahora_iso(),
        })

    def handle_manual_sync(self):
        """Sincronizacion manual: muta estado, por eso exige editar_metricas."""
        sesion = self.exigir("editar_metricas")
        if sesion is None:
            return
        try:
            procesos = self._consultar_procesos()
        except Exception as e:
            self.send_json_response(
                {"error": f"No se pudo consultar SECOP II: {e}",
                 "codigo": "fuente_no_disponible"}, 503)
            return
        registrar_accion(sesion["user_id"])
        self.send_json_response({
            "status": "ok",
            "procesos": len(procesos),
            "actualizado": ahora_iso(),
        })

    def handle_get_notifications(self):
        """Lista de notificaciones. Disponible para los dos roles."""
        if self.exigir("ver_notificaciones") is None:
            return
        try:
            notificaciones = leer_notificaciones()
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)
            return
        self.send_json_response({
            "notificaciones": notificaciones,
            "sin_leer": sum(1 for n in notificaciones if not n.get("leida")),
        })

    def handle_mark_notification(self, payload: dict):
        """Marca una notificacion como leida, o todas si no se indica cual."""
        if self.exigir("ver_notificaciones") is None:
            return
        try:
            notificaciones = leer_notificaciones()
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)
            return

        objetivo = payload.get("id")
        if objetivo:
            if not any(n["id"] == objetivo for n in notificaciones):
                self.send_json_response(
                    {"error": "No existe esa notificacion",
                     "codigo": "no_encontrada"}, 404)
                return
            for n in notificaciones:
                if n["id"] == objetivo:
                    n["leida"] = True
        else:
            for n in notificaciones:
                n["leida"] = True

        guardar_notificaciones(notificaciones)
        self.send_json_response({
            "status": "ok",
            "sin_leer": sum(1 for n in notificaciones if not n.get("leida")),
        })

    def handle_get_stats(self):
        self.send_json_response({
            "status": "online",
            "db_connected": True,
            "secop_api": "https://www.datos.gov.co/resource/p6dx-8zbt.json",
            "cron_schedule": "00:45, 10:00, 13:30, 20:00 COT"
        })


class ServidorReutilizable(socketserver.TCPServer):
    """TCPServer que reutiliza la direccion al reiniciar.

    Sin esto, tras apagar el servidor el puerto queda en TIME_WAIT y el
    siguiente arranque falla con "Address already in use" durante ~60s.
    """
    allow_reuse_address = True


def run_server(port=PORT):
    server_address = ('', port)
    httpd = ServidorReutilizable(server_address, SecopMonitorHandler)
    print("===========================================================")
    print(f"[OK] SECOP Monitor activo en http://localhost:{port}")
    print("===========================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
        httpd.server_close()


if __name__ == "__main__":
    run_server()
