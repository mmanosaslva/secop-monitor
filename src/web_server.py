import http.server
import socketserver
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
import urllib.parse
from contextlib import contextmanager
from datetime import datetime, timezone
from http.cookies import SimpleCookie
from typing import Dict, Optional

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Safe imports for dependencies that might be missing in local system python
try:
    from src.filters.engine import FilterEngine, load_config
    HAS_BACKEND_DEPS = True
except ModuleNotFoundError as e:
    HAS_BACKEND_DEPS = False
    print(f"[SECOP WebServer Warning] Dependencias locales no instaladas completamente ({e}). Usando modo interactivo directo.")


PORT = int(os.environ.get("PORT", 8080))
WEB_DIR = os.path.join(os.path.dirname(__file__), "web")
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config", "client_config.json")
# Semilla versionada vs estado en ejecucion.
# config/ guarda la semilla inicial y NO se toca; data/ guarda lo que la
# aplicacion escribe (accesos, acciones, notificaciones leidas) y esta fuera
# del control de versiones. Asi usar la aplicacion no ensucia el repo ni
# rompe las pruebas.
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
SEED_DIR = os.path.join(PROJECT_ROOT, "config")
USERS_PATH = os.path.join(DATA_DIR, "users.json")

# Base de datos del motor (Neon). La web la LEE para mostrar lo que hizo el
# cron; solo escribe que notificaciones vio cada usuario.
try:
    from src.config import DATABASE_URL
    from src.database.connection import get_connection, migrar_trazabilidad
    from src import actividad
except ModuleNotFoundError:
    DATABASE_URL = None


class SinBaseDeDatos(Exception):
    """La web no tiene DATABASE_URL: no hay de donde leer la actividad."""


@contextmanager
def conexion_motor():
    if not DATABASE_URL:
        raise SinBaseDeDatos()
    conn = get_connection(DATABASE_URL)
    try:
        yield conn
    finally:
        conn.close()


def preparar_base() -> None:
    """Crea (si faltan) las columnas y tablas de trazabilidad. Solo agrega.

    El cron las crea tambien, pero corre el codigo de main: hasta que este
    cambio llegue alli, la web no puede esperar a que el cron migre.
    """
    if not DATABASE_URL:
        print("[SECOP WebServer] Sin DATABASE_URL: la actividad del monitor no "
              "estara disponible.", flush=True)
        return
    try:
        with conexion_motor() as conn:
            cursor = conn.cursor()
            migrar_trazabilidad(cursor)
            cursor.close()
    except Exception as e:
        print(f"[SECOP WebServer] No se pudo preparar la base: {e}", flush=True)


CONTRASENA_POR_DEFECTO = "Cambiar2026*"


def migrar_usuarios_sin_contrasena() -> None:
    """Da una contrasena inicial a los usuarios que aun no tienen hash.

    Necesario para los datos creados antes de que existiera la autenticacion:
    sin esto no podrian iniciar sesion nunca.
    """
    if not os.path.exists(USERS_PATH):
        return
    usuarios = leer_usuarios()
    migrados = [u["correo"] for u in usuarios if not u.get("password_hash")]
    if not migrados:
        return
    for u in usuarios:
        if not u.get("password_hash"):
            u["password_hash"], u["salt"] = hash_contrasena(CONTRASENA_POR_DEFECTO)
    guardar_usuarios(usuarios)
    print(f"[SECOP WebServer] {len(migrados)} usuario(s) sin contraseña recibieron "
          f"la inicial '{CONTRASENA_POR_DEFECTO}'. Cambiala al entrar: "
          + ", ".join(migrados), flush=True)


def sembrar_datos() -> None:
    """Copia la semilla a data/ la primera vez que se arranca."""
    os.makedirs(DATA_DIR, exist_ok=True)
    for nombre in ("users.json",):
        destino = os.path.join(DATA_DIR, nombre)
        if not os.path.exists(destino):
            origen = os.path.join(SEED_DIR, nombre)
            with open(origen, "r", encoding="utf-8") as f_in, \
                 open(destino, "w", encoding="utf-8") as f_out:
                f_out.write(f_in.read())

COOKIE_NAME = "secop_sid"

# Derivacion de contrasenas: PBKDF2-HMAC-SHA256, todo de la biblioteca estandar.
PBKDF2_ITERACIONES = 200_000
LONGITUD_MINIMA_CONTRASENA = 8

# Freno a la fuerza bruta: tras N fallos seguidos, el correo queda bloqueado
# unos segundos. Es en memoria, suficiente para este MVP de un solo proceso.
MAX_INTENTOS = 5
BLOQUEO_SEGUNDOS = 60
_intentos_fallidos = {}  # correo -> (numero_de_fallos, momento_del_ultimo)


def hash_contrasena(contrasena: str, salt: str = None):
    """Devuelve (hash_hex, salt_hex). Genera salt nuevo si no se pasa uno."""
    if salt is None:
        salt = secrets.token_hex(16)
    derivado = hashlib.pbkdf2_hmac(
        "sha256", contrasena.encode("utf-8"), bytes.fromhex(salt),
        PBKDF2_ITERACIONES)
    return derivado.hex(), salt


def verificar_contrasena(contrasena: str, hash_esperado: str, salt: str) -> bool:
    """Comparacion en tiempo constante, para no filtrar informacion por el reloj."""
    if not contrasena or not hash_esperado or not salt:
        return False
    try:
        calculado, _ = hash_contrasena(contrasena, salt)
    except ValueError:
        return False
    return hmac.compare_digest(calculado, hash_esperado)


def esta_bloqueado(correo: str) -> int:
    """Segundos que faltan para poder reintentar. 0 si no esta bloqueado."""
    registro = _intentos_fallidos.get(correo)
    if not registro:
        return 0
    fallos, ultimo = registro
    if fallos < MAX_INTENTOS:
        return 0
    restante = int(BLOQUEO_SEGUNDOS - (time.time() - ultimo))
    if restante <= 0:
        _intentos_fallidos.pop(correo, None)
        return 0
    return restante


def anotar_fallo(correo: str) -> None:
    fallos, _ = _intentos_fallidos.get(correo, (0, 0))
    _intentos_fallidos[correo] = (fallos + 1, time.time())


def limpiar_fallos(correo: str) -> None:
    _intentos_fallidos.pop(correo, None)

# ==========================================================================
# Roles y permisos — única fuente de verdad del backend.
# El frontend replica este mapa en app.js (funcion puede()), pero la decision
# que vale es esta: el render puede ocultar, solo el backend autoriza.
# ==========================================================================
# La interfaz es una ventana de solo lectura sobre el cron: ningun rol puede
# lanzarlo ni cambiar lo que filtra. El admin ve mas detalle y gestiona las
# cuentas de la propia aplicacion.
PERMISOS_USUARIO = {
    "ver_metricas",
    "ver_arquitectura",
    "ver_notificaciones",
    "ver_perfil_cliente",
    "ver_actividad",
}

PERMISOS_ADMIN = PERMISOS_USUARIO | {
    "ver_detalle_tecnico",
    "ver_configuracion",
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
        elif path == "/api/config":
            self.handle_get_config()
        elif path == "/api/actividad":
            self.handle_actividad()
        elif path.startswith("/api/actividad/ejecucion/"):
            self.handle_detalle_ejecucion(path.rsplit("/", 1)[-1])
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
        elif path == "/api/auth/password":
            self.handle_change_password(payload)
        elif path == "/api/filter/test":
            self.handle_test_filter(payload)
        elif path == "/api/config":
            self.send_json_response({
                "error": "La configuración es de solo lectura: se cambia en "
                         "config/client_config.json del repositorio.",
                "codigo": "solo_lectura",
            }, 405)
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

        contrasena = datos.get("contrasena")
        if id_actual is None and not contrasena:
            return "La contraseña es obligatoria al crear un usuario"
        if contrasena and len(contrasena) < LONGITUD_MINIMA_CONTRASENA:
            return (f"La contraseña debe tener al menos "
                    f"{LONGITUD_MINIMA_CONTRASENA} caracteres")
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
        clave, salt = hash_contrasena(payload["contrasena"])
        nuevo = {
            "id": f"u-{max(numeros, default=0) + 1:03d}",
            "nombre": payload["nombre"].strip(),
            "correo": payload["correo"].strip().lower(),
            "rol": payload["rol"],
            "estado": payload.get("estado", "activo"),
            "password_hash": clave,
            "salt": salt,
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
            # En la edicion la contrasena es opcional: si viene vacia, se
            # conserva la que ya tenia.
            "contrasena": payload.get("contrasena") or None,
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
        if datos["contrasena"]:
            actual["password_hash"], actual["salt"] = hash_contrasena(
                datos["contrasena"])
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
        """Autentica por correo y contrasena.

        Los errores son deliberadamente genericos: distinguir "no existe ese
        correo" de "contrasena incorrecta" permitiria enumerar usuarios.
        """
        correo = (payload.get("correo") or "").strip().lower()
        contrasena = payload.get("contrasena") or ""

        if not correo or not contrasena:
            self.send_json_response(
                {"error": "Indica tu correo y tu contraseña",
                 "codigo": "faltan_datos"}, 400)
            return

        espera = esta_bloqueado(correo)
        if espera:
            self.send_json_response({
                "error": f"Demasiados intentos fallidos. Reintenta en {espera} segundos.",
                "codigo": "bloqueado",
                "segundos": espera,
            }, 429)
            return

        usuarios = leer_usuarios()
        elegido = next(
            (u for u in usuarios if u["correo"].lower() == correo), None)

        credenciales_validas = elegido is not None and verificar_contrasena(
            contrasena, elegido.get("password_hash"), elegido.get("salt"))

        if not credenciales_validas:
            anotar_fallo(correo)
            self.send_json_response(
                {"error": "Correo o contraseña incorrectos",
                 "codigo": "credenciales_invalidas"}, 401)
            return

        # La cuenta inactiva si se distingue: quien acerto la contrasena ya
        # demostro ser el titular, y necesita saber por que no entra.
        if elegido["estado"] != "activo":
            self.send_json_response(
                {"error": "Tu cuenta está desactivada. Contacta a un administrador.",
                 "codigo": "cuenta_inactiva"}, 403)
            return

        limpiar_fallos(correo)

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

    def handle_change_password(self, payload: dict):
        """Cambio de la propia contrasena. Exige la actual."""
        sesion = self.sesion_actual()
        if sesion is None:
            self.send_json_response(
                {"error": "No hay sesion activa", "codigo": "sin_sesion"}, 401)
            return

        actual = payload.get("actual") or ""
        nueva = payload.get("nueva") or ""

        if len(nueva) < LONGITUD_MINIMA_CONTRASENA:
            self.send_json_response({
                "error": f"La nueva contraseña debe tener al menos "
                         f"{LONGITUD_MINIMA_CONTRASENA} caracteres",
                "codigo": "contrasena_debil"}, 400)
            return

        usuarios = leer_usuarios()
        usuario = next((u for u in usuarios if u["id"] == sesion["user_id"]), None)
        if usuario is None:
            self.send_json_response(
                {"error": "La cuenta ya no existe", "codigo": "no_encontrado"}, 404)
            return

        if not verificar_contrasena(actual, usuario.get("password_hash"),
                                    usuario.get("salt")):
            self.send_json_response(
                {"error": "La contraseña actual no es correcta",
                 "codigo": "credenciales_invalidas"}, 403)
            return

        usuario["password_hash"], usuario["salt"] = hash_contrasena(nueva)
        guardar_usuarios(usuarios)
        registrar_accion(usuario["id"])
        self.send_json_response({"status": "ok"})

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

    # ----------------------------------------------------------------------
    # Actividad del monitor (lectura de la base del cron)
    # ----------------------------------------------------------------------
    def _con_base(self, consulta):
        """Ejecuta `consulta(conn)` y traduce los fallos a respuestas claras."""
        try:
            with conexion_motor() as conn:
                return True, consulta(conn)
        except SinBaseDeDatos:
            self.send_json_response({
                "error": "La interfaz no tiene acceso a la base de datos del monitor.",
                "codigo": "sin_base_de_datos",
            }, 503)
        except Exception as e:
            self.send_json_response({
                "error": f"No se pudo consultar la base de datos del monitor: {e}",
                "codigo": "base_no_disponible",
            }, 503)
        return False, None

    def handle_actividad(self):
        sesion = self.exigir("ver_actividad")
        if sesion is None:
            return
        es_admin = puede(sesion["rol"], "ver_detalle_tecnico")
        ahora = datetime.now(timezone.utc)
        ok, datos = self._con_base(lambda conn: actividad.panel(conn, ahora, es_admin))
        if ok:
            self.send_json_response(datos)

    def handle_detalle_ejecucion(self, job_id: str):
        sesion = self.exigir("ver_actividad")
        if sesion is None:
            return
        if not job_id.isdigit():
            self.send_json_response({"error": "Ejecución no válida"}, 400)
            return
        es_admin = puede(sesion["rol"], "ver_detalle_tecnico")
        ok, datos = self._con_base(lambda conn: actividad.detalle(conn, int(job_id), es_admin))
        if not ok:
            return
        if datos is None:
            self.send_json_response({"error": "No existe esa ejecución"}, 404)
            return
        self.send_json_response(datos)

    def handle_get_metrics(self):
        """KPIs del panel, calculados sobre lo que registro el cron.

        Devuelve solo conteos: el detalle de cada proceso vive en la vista de
        actividad.
        """
        if self.exigir("ver_metricas") is None:
            return
        ahora = datetime.now(timezone.utc)
        ok, datos = self._con_base(lambda conn: actividad.metricas(conn, ahora))
        if ok:
            self.send_json_response(datos)

    def _eventos(self, conn, sesion):
        return actividad.eventos_de(
            conn, datetime.now(timezone.utc),
            puede(sesion["rol"], "ver_detalle_tecnico"), sesion["user_id"])

    def handle_get_notifications(self):
        """Lo que hizo el cron desde la ultima visita. Ambos roles."""
        sesion = self.exigir("ver_notificaciones")
        if sesion is None:
            return
        ok, eventos = self._con_base(lambda conn: self._eventos(conn, sesion))
        if ok:
            self.send_json_response({
                "notificaciones": eventos,
                "sin_leer": sum(1 for n in eventos if not n["leida"]),
            })

    def handle_mark_notification(self, payload: dict):
        """Marca un evento como visto por este usuario, o todos los actuales."""
        sesion = self.exigir("ver_notificaciones")
        if sesion is None:
            return
        objetivo = payload.get("id")

        def marcar(conn):
            eventos = self._eventos(conn, sesion)
            claves = [e["id"] for e in eventos]
            if objetivo is not None:
                if objetivo not in claves:
                    return None
                claves = [objetivo]
            actividad.marcar_leidos(conn, sesion["user_id"], claves)
            return len([e for e in eventos if not e["leida"] and e["id"] not in claves])

        ok, sin_leer = self._con_base(marcar)
        if not ok:
            return
        if sin_leer is None:
            self.send_json_response(
                {"error": "No existe esa notificacion", "codigo": "no_encontrada"}, 404)
            return
        self.send_json_response({"status": "ok", "sin_leer": sin_leer})


class ServidorReutilizable(socketserver.ThreadingTCPServer):
    """ThreadingTCPServer que reutiliza la direccion al reiniciar y atiende
    peticiones en hilos concurrentes para evitar bloqueos del navegador.
    """
    allow_reuse_address = True
    daemon_threads = True


def run_server(port=PORT):
    sembrar_datos()
    preparar_base()
    migrar_usuarios_sin_contrasena()
    server_address = ('', port)
    httpd = ServidorReutilizable(server_address, SecopMonitorHandler)
    print("===========================================================", flush=True)
    print(f"[OK] SECOP Monitor activo en http://localhost:{port}", flush=True)
    print("===========================================================", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
        httpd.server_close()


if __name__ == "__main__":
    run_server()
