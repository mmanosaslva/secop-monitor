# SECOP Monitor

Monitoreo automático de contratación pública en SECOP II (Colombia). Detecta
procesos relevantes por departamento, modalidad y palabras clave, y envía
notificaciones por correo con badges de certificación.

El proyecto son **dos piezas que se levantan por separado**:

| Pieza | Qué hace | Necesita base de datos |
|-------|----------|------------------------|
| **Motor** (`src/main.py`) | Consulta SECOP II, filtra, deduplica y envía correos. Lo dispara el cron. | Sí (Neon PostgreSQL) |
| **Interfaz web** (`src/web_server.py`) | Panel de métricas, monitoreo en vivo, notificaciones y gestión de usuarios. | **No** |

---

## Inicio rápido

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python src/web_server.py          # → http://localhost:8080
```

Y entra con estas credenciales:

| Correo | Contraseña | Rol | Estado |
|--------|-----------|-----|--------|
| `admin@secopmonitor.co` | `Admin2026*` | **Administrador** | Activo |
| `cliente@secopmonitor.co` | `Cliente2026*` | Usuario | Activo |
| `analista@secopmonitor.co` | `Analista2026*` | Usuario | Activo |
| `supervisora@secopmonitor.co` | `Supervisora2026*` | Administrador | **Inactivo** |

La cuenta de la supervisora está desactivada a propósito: sirve para comprobar
que una cuenta inactiva no entra aunque la contraseña sea correcta.

**Estas credenciales son públicas** — están en este archivo y en el repositorio.
Cámbialas desde *Contraseña*, en el encabezado, antes de usar la aplicación con
datos reales. Para volver a ellas en cualquier momento: `rm -rf data/`.

La interfaz web no necesita base de datos ni `.env`. El motor sí; eso se
explica [más abajo](#levantar-el-motor).

---

## Requisitos

- Python 3.11 o superior
- Nada más para la interfaz web
- Para el motor: una base Neon PostgreSQL y una clave de Brevo

## Instalación

```bash
git clone git@github.com:mmanosaslva/secop-monitor.git
cd secop-monitor
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## Levantar la interfaz web

Es la vía rápida: **no necesita `.env` ni base de datos.**

```bash
source .venv/bin/activate
python src/web_server.py
```

Abre <http://localhost:8080>.

El puerto se cambia con la variable `PORT`, útil si el 8080 ya está ocupado:

```bash
PORT=8099 python src/web_server.py
```

> **En WSL2**, el puerto 8080 puede estar tomado por un proceso del lado Windows
> aunque `ss -ltn` no muestre nada dentro de Linux. Si ves
> `Address already in use` con el puerto aparentemente libre, usa otro puerto.

### Entrar a la aplicación

La aplicación pide **correo y contraseña**. El rol y los permisos los determina
la cuenta con la que entras, no una elección en la pantalla de acceso.

Las credenciales iniciales están en [Inicio rápido](#inicio-rápido).

#### Qué ve cada rol

| Rol | Módulos |
|-----|---------|
| **Usuario** | Panel de Métricas (solo lectura) y ¿Cómo Funciona por Dentro?, más el desplegable de notificaciones |
| **Administrador** | Todo lo anterior + Monitoreo en Vivo, Configuración del Cliente y Gestión de Usuarios |

**Solo el administrador puede crear, editar, activar, desactivar o eliminar
usuarios**, y es el único que puede asignar o restablecer contraseñas de otras
cuentas. Cualquier usuario puede cambiar la suya propia.

### Cómo funciona la autenticación

- Las contraseñas se guardan con **PBKDF2-HMAC-SHA256**, 200 000 iteraciones y
  un salt aleatorio distinto por usuario. Nunca se almacenan en claro ni se
  envían al navegador.
- La sesión es un token opaco en una cookie `HttpOnly` con `SameSite=Strict`.
- Un correo inexistente y una contraseña incorrecta devuelven **el mismo
  error**, para que nadie pueda averiguar qué correos están registrados.
- Tras **5 intentos fallidos** el correo queda bloqueado **60 segundos**.
- Mínimo de 8 caracteres al crear o cambiar una contraseña.

#### Limitaciones que debes conocer

Es un MVP y conviene ser explícito sobre lo que **no** hace:

- Las sesiones viven en memoria: al reiniciar el servidor, todos salen.
- El bloqueo por intentos fallidos también es en memoria y por proceso.
- No hay recuperación de contraseña por correo. Si pierdes la del único
  administrador, borra `data/` para volver a las credenciales iniciales.
- La cookie no lleva `Secure` porque el servidor es HTTP. **Detrás de HTTPS hay
  que añadirlo.**

---

---

## Levantar el motor

A diferencia de la interfaz, **el motor sí necesita configuración**.

Copia `.env.example` a `.env` y complétalo:

```bash
cp .env.example .env
```

```bash
DATABASE_URL=postgresql://user:pass@ep-xxx.neon.tech/neondb?sslmode=require
BREVO_API_KEY=xkeysib-...
SENDER_EMAIL=oportunidades.secop@outlook.com
SENDER_NAME=SECOP Monitor
ADMIN_EMAIL=tu@email.com
STEALTH_MODE=false
SECOP_APP_TOKEN=                  # opcional: sube el límite de la API de datos.gov.co
```

Ejecución local:

```bash
source .venv/bin/activate
python -m src.main
```

En producción lo dispara GitHub Actions cuatro veces al día (00:45, 10:00,
13:30 y 20:00 COT). Manualmente: **GitHub → Actions → SECOP Monitor → Run
workflow**.

---

## Roles y permisos

El control de acceso vive en `src/web_server.py`, en el mapa `PERMISOS`. El
frontend lo replica en la función `puede()` de `app.js` **solo para decidir qué
pintar**: la decisión que vale es la del servidor, que rechaza la petición
aunque el botón se haya reconstruido desde el inspector.

| Permiso | usuario | admin |
|---------|:-------:|:-----:|
| `ver_metricas` | ✅ | ✅ |
| `ver_arquitectura` | ✅ | ✅ |
| `ver_notificaciones` | ✅ | ✅ |
| `ver_perfil_cliente` | ✅ | ✅ |
| `editar_metricas` | — | ✅ |
| `ver_monitoreo` | — | ✅ |
| `editar_configuracion` | — | ✅ |
| `gestionar_usuarios` | — | ✅ |
| `probar_filtros` | — | ✅ |

### Endpoints

Sin sesión responden **401**; con sesión pero sin permiso, **403**.

| Método y ruta | Permiso |
|---------------|---------|
| `POST /api/auth/login` · `POST /api/auth/logout` | público |
| `GET /api/auth/me` | sesión activa |
| `POST /api/auth/password` | sesión activa (exige la contraseña actual) |
| `GET /api/stats` | público |
| `GET /api/config` | `ver_perfil_cliente` |
| `POST /api/config` | `editar_configuracion` |
| `GET /api/metrics` | `ver_metricas` |
| `POST /api/sync` | `editar_metricas` |
| `GET /api/secop/live` | `ver_monitoreo` |
| `POST /api/filter/test` | `probar_filtros` |
| `GET /api/notifications` · `POST /api/notifications/read` | `ver_notificaciones` |
| `GET\|POST /api/users` · `PUT\|DELETE /api/users/{id}` | `gestionar_usuarios` |

`/api/metrics` devuelve solo conteos agregados y `/api/secop/live` la lista de
procesos: por eso el rol usuario ve los números del panel sin poder consultar
los procesos uno a uno.

---

## Configuración

### `config/client_config.json` — reglas de filtrado

```json
{
  "name": "Cliente Textil Caribe",
  "email": "cliente@email.com",
  "departments": ["Atlántico", "Bolívar", "Magdalena", "Córdoba", "Sucre", "La Guajira", "Cesar"],
  "keywords": ["uniforme", "ropa deportiva", "vestuario", "calzado", "dotacion", "textil"],
  "unspsc_codes": ["V1.53102700", "V1.53102710"],
  "certification_keywords": ["mujer lider", "equidad de genero", "pyme"],
  "modalidad_keywords": ["mínima cuantía"]
}
```

### Semilla y estado: `config/` frente a `data/`

- **`config/users.json` y `config/notifications.json`** son la **semilla**
  versionada. La aplicación no los modifica nunca.
- **`data/`** guarda el **estado en ejecución** (accesos, acciones,
  notificaciones leídas, usuarios creados). Está en `.gitignore`, así que usar
  la aplicación no ensucia el repositorio.

En el primer arranque, `data/` se crea copiando la semilla. Para volver al
estado inicial basta con borrar la carpeta:

```bash
rm -rf data/
python src/web_server.py
```

### Lógica de filtrado

Un proceso se notifica si cumple las tres condiciones:

1. El departamento está en la lista del cliente
2. La modalidad es "mínima cuantía"
3. Coincide una palabra clave **o** un código UNSPSC

Las certificaciones (mujer líder, equidad de género, PYME) son badges
informativos, no un requisito.

---

## Tests

```bash
source .venv/bin/activate
pytest -q
```

**105 pruebas.** El motor (filtros, notificaciones, base de datos, fuente SECOP,
integración y aceptación) y el control de acceso del servidor web, que levanta el
servidor real y comprueba que rechaza por HTTP, no que el botón esté oculto.

> `pytest` debe ejecutarse con el intérprete del entorno virtual. Si lo invocas
> con el Python del sistema verás `No module named pytest`; usa
> `./.venv/bin/python -m pytest -q`.

Los warnings sobre `PytestUnknownMarkWarning` (`acceptance`, `integration`,
`slow`) son ruido conocido: faltan registrar esas marcas, no son fallos.

---

## Estructura

```
secop-monitor/
├── .github/workflows/secop.yml     # Cron de GitHub Actions
├── config/
│   ├── client_config.json          # Reglas de filtrado
│   ├── users.json                  # Usuarios y su uso
│   └── notifications.json          # Notificaciones
├── src/
│   ├── main.py                     # Punto de entrada del motor
│   ├── config.py                   # Variables de entorno
│   ├── web_server.py               # Servidor web, sesiones y permisos
│   ├── web/
│   │   ├── index.html              # Interfaz
│   │   ├── app.js                  # Lógica y control de permisos del render
│   │   └── styles.css              # Estilos
│   ├── sources/secop.py            # API de SECOP II
│   ├── filters/engine.py           # Motor de filtros
│   ├── database/                   # Neon DB y CRUD
│   └── notifications/email.py      # Correo vía Brevo
├── tests/
├── design.md                       # Sistema de diseño Plataforma50
├── TAREAS.md                       # Plan de trabajo por fases
└── prompts.md                      # Prompts de ejecución
```

## Ramas

| Rama | Contenido |
|------|-----------|
| `main` | Motor, tests y configuración. **No contiene la interfaz web.** |
| `frontend` | Rama de trabajo: interfaz completa con roles y permisos |
| `simulador` | Archivo del Simulador del Motor, retirado de la interfaz |
| `monitoreo` | Prevista: solo el módulo de Monitoreo en Vivo |

El plan de trabajo y su estado están en [`TAREAS.md`](./TAREAS.md).
