# SECOP Monitor

Monitoreo automático de contratación pública en SECOP II (Colombia). Detecta
procesos relevantes por departamento, modalidad y palabras clave, y envía
notificaciones por correo con badges de certificación.

El proyecto son **dos piezas que se levantan por separado**:

| Pieza | Qué hace | Necesita base de datos |
|-------|----------|------------------------|
| **Motor** (`src/main.py`) | Consulta SECOP II, filtra, deduplica y envía correos. Lo dispara el cron. | Sí (Neon PostgreSQL) |
| **Interfaz web** (`src/web_server.py`) | Ventana de **solo lectura** sobre el cron: qué ciclos corrieron, qué analizaron y qué correos enviaron. Más la gestión de usuarios de la propia app. | Sí, para leer (la misma de Neon) |

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

La interfaz **lee la base de datos del motor**: necesita `DATABASE_URL` en `.env`
(la misma que usa el cron). Sin ella arranca igual, entra y gestiona usuarios,
pero la actividad, las métricas y las notificaciones dicen que no hay acceso a
la base.

Al arrancar crea en esa base, si faltan, las columnas y tablas de trazabilidad
(ver [Cómo se sigue cada ciclo](#cómo-se-sigue-cada-ciclo)). Solo agrega: no
borra ni modifica datos.

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
| **Usuario** (el cliente) | Panel de Métricas, ¿Cómo Funciona por Dentro? y Actividad del Monitor, más la campana con las oportunidades encontradas |
| **Administrador** | Todo lo anterior con detalle técnico (motivos de descarte, logs de GitHub, ejecuciones locales y manuales, alertas de ciclos fallidos u omitidos y de correos que no llegaron), más Configuración del Cliente y Gestión de Usuarios |

**Nadie puede modificar el monitor desde la web**: no se lanza el cron, no se
cambian los filtros. La configuración se consulta en la web y se cambia en
`config/client_config.json` del repositorio.

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

### La interfaz

Sigue el sistema de diseño Plataforma50 ([`design.md`](./design.md)): tema
oscuro, una sola familia tipográfica (Archivo) y un único acento azul.

- **Encabezado:** el logo a la izquierda y, a la derecha, la campana de
  notificaciones, el nombre y el rol de la sesión, *Contraseña* y *Cerrar
  sesión*. En pantallas estrechas los controles bajan a su propia fila.
- **Navegación:** la genera `app.js` según los permisos del rol. Cada pestaña es
  una opción separada; la activa lleva fondo y borde azul. Si no caben, la
  barra se desplaza en horizontal.
- **Formularios** (configuración del cliente, crear o editar usuario, cambiar
  contraseña): comparten la clase `.formulario`, con el label sobre el campo,
  campos al ancho disponible y el foco visible.
- **Crear o editar usuario:** el botón dice lo que va a pasar (*Crear usuario*
  o *Guardar cambios*). Bajo Rol y Estado se explica qué implica cada opción, y
  la contraseña se puede mostrar u ocultar. Al editar, dejarla vacía conserva
  la actual.
- **Cambiar mi contraseña** (ambos roles): la misma estructura que el modal de
  usuario, con cada contraseña visible a demanda y el botón *Cambiar
  contraseña*.
- Los dos modales se cierran con *Cancelar*, con la ×, con Escape o al pulsar
  fuera de ellos.
- El encabezado, la navegación y los modales son **iguales para los dos
  roles**. Solo cambia lo que el rol autoriza: qué pestañas aparecen y el
  color del chip de rol.
- `index.html` carga `styles.css` y `app.js` con `?v=<fecha>`. Cambia ese valor
  al modificarlos para que el navegador no use una copia vieja.

### Actividad del monitor

Es la vista central y la ven los dos roles:

- **El día.** Un eje de 24 h con los cuatro ciclos: una marca hueca en la hora
  programada y un punto en la hora en que GitHub lo corrió de verdad. El tramo
  entre ambos es el retraso. Debajo, cada ciclo con su estado: *Completado*,
  *En curso*, *En cola en GitHub*, *Esperando a GitHub*, *Programado*, *Falló*,
  *Sin terminar* o *No se ejecutó*.
- **La ejecución seleccionada** (por defecto, la última): procesos analizados,
  coincidencias, nuevos y correos enviados; la lista de procesos que
  coincidieron, con el motivo y el estado de entrega de su correo. El admin ve
  además por qué se descartaron los demás y el enlace al log en GitHub.
- **Últimos 7 días**, una fila por día y una columna por ciclo. Cada celda abre
  su ejecución.
- **Todas las ejecuciones** (solo admin), incluidas las manuales y las locales.

La vista se actualiza sola cada 30 s mientras está abierta, y la campana cada
minuto.

#### Qué muestra la campana

| Evento | Quién lo ve |
|--------|-------------|
| Oportunidad nueva, con el estado de su correo | Los dos roles |
| Un ciclo falló o quedó sin terminar | Admin |
| Un ciclo no se ejecutó (pasaron 8 h sin que GitHub lo corriera) | Admin |
| Un correo no se pudo enviar, rebotó, fue bloqueado o marcado como spam | Admin |

Lo leído es **de cada usuario** (tabla `notification_reads`). Es lo único que
escribe la interfaz, y no afecta al motor.

### Cómo se sigue cada ciclo

La interfaz combina dos fuentes:

- **GitHub Actions** dice *cuándo* corrió el workflow y cómo terminó. Se consulta
  su API pública, con caché de 2 minutos. `GITHUB_TOKEN` es opcional y solo sube
  el límite de 60 a 5 000 consultas por hora.
- **La base de datos** dice *qué hizo* cada ejecución. El motor registra ahora:

| Dónde | Qué |
|-------|-----|
| `job_runs` | Run de GitHub y su enlace, qué lo disparó, a qué ciclo corresponde, a quién se enviaron los correos, si iba en modo silencioso, cuántos procesos eran nuevos y un resumen de descartes por motivo |
| `run_matches` | Cada proceso que coincidió en cada ejecución, si era nuevo y por qué coincidió |
| `notifications` | Qué ejecución envió el correo, el `messageId` de Brevo y el estado de entrega |

**Estado de entrega.** Al final de cada ciclo, el motor pregunta a Brevo por los
correos de los últimos 7 días: *enviado*, *entregado*, *abierto*, *diferido*,
*rebotado*, *bloqueado* o *spam*. Por eso el estado de un correo se actualiza en
el ciclo siguiente. No se usa el webhook de Brevo porque la interfaz no está
publicada en internet.

**Retrasos de GitHub.** En la capa gratuita, GitHub corre los cron programados
con 4 a 6 h de retraso (observado en este repositorio). Un ciclo sin ejecución
aparece como *Esperando a GitHub* durante 8 h, y solo después como *No se
ejecutó*. El margen está en `src/ciclos.py`.

**Ejecuciones anteriores a este registro.** Se enlazan a su run de GitHub por la
hora y se asignan a los ciclos en orden. De ellas se conocen los totales y los
procesos nuevos, no todas sus coincidencias; la vista lo indica. Las filas de
`job_runs` sin run de GitHub son ejecuciones locales (pruebas o desarrollo): el
cliente no las ve y el admin las ve marcadas como *Local*.

> **El cron corre el código de `main`.** Mientras estos cambios no lleguen a
> `main`, los ciclos nuevos no registran el detalle: la vista funciona, pero
> todas las ejecuciones se ven como las anteriores a este registro.

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
| `ver_actividad` | ✅ | ✅ |
| `ver_detalle_tecnico` | — | ✅ |
| `ver_configuracion` | — | ✅ |
| `gestionar_usuarios` | — | ✅ |
| `probar_filtros` | — | ✅ |

### Endpoints

Sin sesión responden **401**; con sesión pero sin permiso, **403**.

| Método y ruta | Permiso |
|---------------|---------|
| `POST /api/auth/login` · `POST /api/auth/logout` | público |
| `GET /api/auth/me` | sesión activa |
| `POST /api/auth/password` | sesión activa (exige la contraseña actual) |
| `GET /api/config` | `ver_perfil_cliente` |
| `POST /api/config` | nadie: responde **405**, la configuración es de solo lectura |
| `GET /api/metrics` | `ver_metricas` |
| `GET /api/actividad` · `GET /api/actividad/ejecucion/{id}` | `ver_actividad` (con `ver_detalle_tecnico`, la respuesta incluye logs, descartes y ejecuciones locales) |
| `POST /api/filter/test` | `probar_filtros` |
| `GET /api/notifications` · `POST /api/notifications/read` | `ver_notificaciones` |
| `GET\|POST /api/users` · `PUT\|DELETE /api/users/{id}` | `gestionar_usuarios` |

Sin base de datos, los endpoints de actividad, métricas y notificaciones
responden **503** con `"codigo": "sin_base_de_datos"`.

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

- **`config/users.json`** es la **semilla** versionada. La aplicación no lo
  modifica nunca.
- **`data/`** guarda el **estado en ejecución** (accesos, acciones, usuarios
  creados). Está en `.gitignore`, así que usar
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

**141 pruebas, más 2 que se saltan sin base de pruebas.** Cubren:

- El motor: filtros y su motivo, notificaciones, base de datos, fuente SECOP y
  un ciclo completo con la base, SECOP y Brevo simulados.
- La reconstrucción de la actividad (`tests/test_actividad.py`): retrasos de
  GitHub, ciclos omitidos, ejecuciones locales, lo que ve cada rol y que los
  ciclos coinciden con `secop.yml`.
- El control de acceso del servidor web, que levanta el servidor real con una
  base falsa en memoria y comprueba que rechaza por HTTP, no que el botón esté
  oculto.

> **`tests/test_main_integration.py` necesita `TEST_DATABASE_URL`**, una base
> **distinta de la de producción**. Antes usaba `DATABASE_URL`, y cada ejecución
> de las pruebas dejaba filas falsas en `job_runs`. Sin esa variable, las dos
> pruebas se saltan.

> `pytest` debe ejecutarse con el intérprete del entorno virtual. Si lo invocas
> con el Python del sistema verás `No module named pytest`; usa
> `./.venv/bin/python -m pytest -q`.

Los warnings sobre `PytestUnknownMarkWarning` (`acceptance`, `integration`,
`slow`) son ruido conocido: faltan registrar esas marcas, no son fallos.

> **Algunas pruebas consultan la API real de datos.gov.co** y fallan de forma
> intermitente cuando esa API va lenta o no devuelve datos. Están en
> `test_integration.py`, `test_secop_source.py` y `test_acceptance.py`. Si ves
> un fallo ahí, reintenta esa prueba sola antes de darla por regresión:
>
> ```bash
> pytest tests/test_integration.py::test_api_returns_data -q
> ```
>
> Para correr solo lo que no depende de la red:
>
> ```bash
> pytest -q --ignore=tests/test_integration.py --ignore=tests/test_main_integration.py
> ```

---

## Estructura

```
secop-monitor/
├── .github/workflows/secop.yml     # Cron de GitHub Actions
├── config/
│   ├── client_config.json          # Reglas de filtrado
│   └── users.json                  # Usuarios y su uso (semilla)
├── src/
│   ├── main.py                     # Punto de entrada del motor
│   ├── ciclos.py                   # Los 4 ciclos del cron y su hora en Colombia
│   ├── ejecucion.py                # Contexto de GitHub Actions de cada ejecución
│   ├── actividad.py                # Reconstruye la actividad para la web (GitHub + base)
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
| `frontend` | Interfaz con autenticación, roles y permisos |
| `integracion-cron` | La interfaz como ventana de solo lectura sobre el cron, y el registro detallado de cada ciclo en el motor |
| `monitoreo-directo` | Archivo del Monitoreo en Vivo con consulta directa a SECOP, la sincronización manual y el editor de configuración, retirados en `integracion-cron`. No se fusiona. |
| `simulador` | Archivo del Simulador del Motor, retirado de la interfaz. No se fusiona. |

El plan de trabajo y su estado están en [`TAREAS.md`](./TAREAS.md).
