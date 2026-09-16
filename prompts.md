# Prompts de trabajo — mvp_SECOP

Dos prompts listos para copiar y pegar. El plan de ejecución paso a paso está en
[`TAREAS.md`](./TAREAS.md).

**Orden de trabajo: primero la funcionalidad, el diseño al final.**

| # | Prompt | Rama | Estado |
|---|--------|------|--------|
| 1 | Roles, permisos y limpieza | `frontend` | **Completado** (fases 0-6) |
| 2 | Diseño visual Plataforma50 | `frontend` | Siguiente |

### Mapa de ramas

Son tres, y no hay más:

| Rama | Contenido | Estado |
|------|-----------|--------|
| `main` | Motor, tests y config. **No contiene la interfaz web** | **INTOCABLE** — no se modifica sin orden explícita |
| `frontend` | Producto completo: roles, autenticación, métricas, notificaciones, gestión de usuarios | Rama de trabajo |
| `simulador` | Simulador del Motor, preservado íntegro | Archivo — no se fusiona |

El Monitoreo en Vivo **no es una rama**: es un módulo más dentro de `frontend`,
visible solo para el rol admin.

> **`main` no es respaldo de nada de la interfaz.** Verificado: contiene 33
> archivos, ninguno bajo `src/web/`. Toda la web vive solo en `frontend`. Por eso
> cada módulo que se retira necesita su propia rama antes de ser borrado.

---

## Por qué el diseño va al final

1. **La estructura manda sobre el estilo.** Los roles cambian *qué* se renderiza
   (nav condicionado, métricas de solo lectura, tabla de usuarios, campana de
   notificaciones). Diseñar antes de saber qué componentes existen obliga a
   rehacer artboards.
2. **El coste de migrar está medido** (corregido el 2026-09-15). La hoja está
   tokenizada *en parte*: la mayoría de reglas consume variables, pero quedan
   **16 colores en duro fuera de `:root`** (eran 28 antes de retirar el
   previsualizador de correo y el simulador). La migración es sobre todo un
   remapeo de `:root`, más esos 16 casos sueltos que hay que convertir a
   variables. No es una reescritura, pero tampoco es solo cambiar `:root`.
3. **La funcionalidad ya está verificada.** Con 120 pruebas en verde sobre el
   comportamiento, el rediseño solo puede romper lo visual: cualquier fallo de
   lógica lo delata la suite, no el ojo.

---

## Stack de diseño

Lo que se usa para construir la parte visual, y en qué orden interviene:

| Capa | Herramienta | Rol |
|------|-------------|-----|
| Fuente de verdad | `design.md` (181 líneas, rama `frontend`) | Tokens, tipografía, layout, voz y copy. Manda sobre cualquier criterio estético. |
| Autoría visual | Skill `design` de Claude Code (Claude Design embebido) | Genera el canvas multi-artboard y lo publica como Artifact. |
| Edición | Editor de canvas en el Artifact publicado | Selección de elementos, panel de propiedades, texto en línea, deshacer/rehacer, export PNG/PDF. |
| Implementación | `src/web/styles.css` → `:root` | Los tokens del canvas aterrizan como variables CSS `--p50-*`. |
| Estructura | `src/web/index.html`, `src/web/app.js` | Ya definidos por el Prompt 1; el diseño no cambia la estructura, solo la viste. |

**No existe un MCP de Claude Design.** La integración es la skill `design`; los
servidores MCP conectados (Gmail, Calendar, Drive, Notion) no intervienen aquí.

### Tokens Plataforma50 (destino de la migración)

```
--p50-ink         #0B0E14   fondo
--p50-surface     #13171F   tarjetas
--p50-line        #232833   bordes 1px
--p50-text        #F4F6F8   texto
--p50-text-muted  #9AA3B2   texto secundario
--p50-accent      #2F6BFF   acento único
--p50-accent-soft #1B2A4D   acento atenuado
--p50-paper       #FFFFFF   papel
```

---

## Prompt 1 — Roles, permisos y limpieza (rama `frontend`)

```
Trabaja sobre la rama `frontend` del repo mvp_SECOP. Implementa roles y permisos
en la interfaz web (`src/web/index.html`, `src/web/app.js`, `src/web/styles.css`)
y el soporte necesario en `src/web_server.py`.

Esta fase es FUNCIONAL. El rediseño visual va después, en un prompt aparte: no
migres la paleta ni la tipografía todavía.

1. SISTEMA DE ROLES
   - Dos roles: `admin` y `usuario`.
   - Pantalla de acceso que fija el rol de la sesión; el rol se persiste en la
     sesión del navegador y determina qué renderiza el nav.
   - El control de permisos debe aplicarse en el render (no mostrar lo prohibido)
     Y en el backend (rechazar la petición si el rol no autoriza), no solo
     ocultando botones con CSS.

2. PERMISOS POR ROL
   Rol `usuario` — acceso ÚNICAMENTE a:
     - Panel de Métricas (SOLO LECTURA: sin guardar, sin editar, sin sincronizar
       manualmente, sin ejecutar acciones que muten estado).
     - ¿Cómo Funciona por Dentro?
     - El desplegable de Notificaciones.
   Rol `admin` — acceso a todo lo anterior MÁS:
     - Edición de métricas y de configuración (único rol con permiso de escritura).
     - Configuración del Cliente.
     - Gestión y control de todos los usuarios: listado de usuarios, crear,
       editar, activar/desactivar, cambiar rol, y un panel con métricas agregadas
       de uso por usuario (último acceso, acciones realizadas, estado).
     - Monitoreo en Vivo (SECOP II).

3. NOTIFICACIONES
   - Deja de ser un módulo/tab del nav ("Notificación Brevo", index.html L69).
   - Pasa a ser un desplegable: campana en el header con badge de conteo, panel
     flotante con la lista, marcar como leída y estado vacío.
   - Disponible para los dos roles.

4. RETIRAR EL SIMULADOR (ya está preservado en la rama `simulador`)
   - El módulo NO se pierde: la rama `simulador` conserva el estado íntegro
     previo a esta limpieza. Verifícalo antes de borrar:
     `git grep -c 'tab-simulator' simulador -- src/web/index.html`
   - Confirmado eso, quita el tab "Simulador del Motor" (index.html L63) y su
     sección `#tab-simulator` (L379-449) de las vistas de usuario y de admin.
   - Quita `initSimulator()` y `runSimulation()` de `app.js` y sus estilos
     asociados en `styles.css`.

5. DISCIPLINA DE ESTILOS (para que el rediseño posterior sea barato)
   - `styles.css` está tokenizado: los colores solo viven en `:root`. MANTÉN esa
     propiedad. Todo componente nuevo (campana, panel de notificaciones, tabla de
     usuarios, modales, pantalla de acceso, vista de acceso denegado) debe
     consumir las variables existentes (`--sena-*`, `--bg-*`, `--text-*`,
     `--border-color`, `--radius-*`).
   - CERO colores hexadecimales fuera de `:root`. Es la condición que convierte
     el Prompt 2 en un remapeo de tokens en lugar de una reescritura.
   - Usa clases semánticas por función (`.is-readonly`, `.badge-count`), no por
     apariencia (`.verde`, `.texto-grande`).

6. RESTRICCIONES
   - No toques la lógica de negocio de `src/filters/`, `src/sources/`,
     `src/database/` ni `src/notifications/`.
   - Mantén los tests existentes pasando (`pytest`) y añade tests para el
     control de permisos del backend.
   - Commits atómicos por bloque funcional, en español, sobre la rama `frontend`.
```

---

## Prompt 2 — Diseño visual Plataforma50 (rama `frontend`)

```
Diseña el sistema visual completo del aplicativo web SECOP Monitor siguiendo
ESTRICTAMENTE el sistema de diseño de `design.md` (rama `frontend`), y después
impleméntalo en código.

CONTEXTO — la estructura ya está terminada, diseña sobre ESTA, no sobre otra
- Autenticación con correo y contraseña. NO hay selección de rol: el rol lo
  determina la cuenta. Existen pantalla de acceso, modal de cambio de la propia
  contraseña y campo de contraseña en el alta/edición de usuarios.
- Dos roles. El nav del rol USUARIO tiene exactamente dos módulos: Panel de
  Métricas y ¿Cómo Funciona por Dentro?. El de ADMIN añade Monitoreo en Vivo,
  Configuración del Cliente y Gestión de Usuarios.
- Las notificaciones son un desplegable del encabezado, no un módulo del nav.
- El Simulador del Motor ya no existe en la interfaz.
- Código en `src/web/index.html`, `src/web/styles.css`, `src/web/app.js`.
- La interfaz usa estilo SENA (verde #39A900, azul #00324D, Montserrat) y debe
  migrar por completo a Plataforma50.

REGLAS NO NEGOCIABLES
1. Lee `design.md` completo y aplícalo literalmente:
   - Color: `--p50-ink #0B0E14` (fondo), `--p50-surface #13171F` (tarjetas),
     `--p50-line #232833` (bordes 1px), `--p50-text #F4F6F8`,
     `--p50-text-muted #9AA3B2`, `--p50-accent #2F6BFF` (único acento),
     `--p50-accent-soft #1B2A4D`, `--p50-paper #FFFFFF`.
   - UN SOLO acento por pantalla: marca acción (CTA) y estado deseado.
   - Cero degradados decorativos. Bordes de 1px, sin sombras.
   - Tipografía: una sola familia sans geométrica, dos pesos (400/600).
     Titular de sección 40-56px/600/-0.02em, eyebrow 13-14px/500/+0.08em,
     cuerpo 16-18px/1.6, dato o delta 32-48px/600 tabular, numeral `[01]` 13px mono.
   - Layout: 12 columnas, ancho máx ~1280px, gutter 24-32px.
   - Contraste mínimo 4.5:1.
2. ELIMINA el nombre "SECOP II Monitor" del encabezado y "SECOP Monitor v2.0"
   del pie. El encabezado no lleva wordmark de texto: solo el logotipo, las
   píldoras de estado del sistema, la campana de notificaciones y los controles
   de sesión (nombre, chip de rol, Contraseña, Cerrar sesión). El pie conserva
   únicamente la descripción funcional.
   (La línea institucional del SENA y el distintivo "v2.0 Enterprise" ya fueron
   eliminados; no los reintroduzcas.)
3. Voz y copy según §2 de `design.md`: segunda persona, titulares de 4-8
   palabras partidos en dos líneas, eyebrow en minúscula sobre cada titular,
   nada de superlativos vacíos, cada dato con número explícito.
4. `design.md` describe un sitio de marketing; esto es una aplicación de datos.
   Toma de él color, tipografía, voz y componentes (§3, §4, §2, §6) y DEDUCE
   los patrones que le faltan —tabla densa, formulario, modal, desplegable,
   estados de sesión— con las mismas reglas: 1px, sin sombra, un solo acento.
   NO trasplantes la secuencia de la home (hero con video, casos de éxito,
   equipo, FAQ, marquee de aliados): aquí no aplica.

ENTREGA EN DOS CANVAS (no todo en uno: degradaría los últimos artboards)

CANVAS A — núcleo del sistema
  0. Tira de tokens: paleta, escala tipográfica, botón primario y secundario,
     campo de formulario, chip, tarjeta numerada, fila de comparación,
     fila de tabla, modal y estado de error.
  1. *Acceso — formulario de correo y contraseña, con mostrar/ocultar, CTA único
     y microcopy tranquilizador debajo. Incluye sus tres estados de error:
     credenciales inválidas, cuenta desactivada y bloqueo por intentos fallidos.
  2. *Panel de Métricas — rol USUARIO (solo lectura): KPIs en tarjetas numeradas
     `[01]`-`[04]`, distintivo de solo lectura, sin ningún control de edición.
  3. Panel de Métricas — rol ADMIN: mismos KPIs + sincronización manual.
  4. Estados transversales: el nav en ambos roles, estado vacío, estado de
     carga, acceso denegado y el modal de cambio de la propia contraseña.

CANVAS B — módulos (reutiliza los tokens fijados en el Canvas A)
  5. ¿Cómo Funciona por Dentro? — narrativa del motor con el motivo de marca
     "Antes / Ahora": label a la izquierda, "Antes" en neutro apagado, "Ahora"
     en acento.
  6. *Desplegable de Notificaciones — campana con badge de conteo, panel
     flotante, leída / sin leer, estado vacío. NO es un módulo del nav.
  7. Gestión de Usuarios — solo ADMIN: métricas agregadas de uso arriba, tabla
     (avatar, nombre, correo, rol, estado, último acceso, uso), acciones por
     fila, y modal de crear/editar CON campo de contraseña.
  8. Configuración del Cliente — solo ADMIN.
  9. Monitoreo en Vivo — solo ADMIN: tabla de procesos SECOP II con buscador,
     filtro por departamento, filtro por coincidencia y modal de detalle.

Los marcados * llevan además variante móvil de 390px. Desktop a 1440px.
Artboards ordenados por flujo dentro de cada canvas.

IMPLEMENTACIÓN EN CÓDIGO (después de aprobados los dos canvas)
- Sustituye el bloque `:root` de `src/web/styles.css`: los tokens `--sena-*`
  pasan a `--p50-*`.
- Convierte a variables los 16 colores en duro que quedan fuera de `:root`:
  `awk '/^:root/{r=1} r&&/^}/{r=0;next} !r' src/web/styles.css | grep -nE '#[0-9A-Fa-f]{3,8}'`
- Renombra los 82 selectores con prefijo `.sena-` y sustituye el logotipo.
- Ajusta la escala tipográfica, quita sombras y degradados, deja bordes de 1px.
- Aplica la regla 2 en `index.html`.
- Verifica contraste 4.5:1 en todo texto.
- `pytest -q` debe seguir en verde: 120 pruebas. El rediseño no cambia
  comportamiento, así que un fallo señala una regresión... salvo en las pruebas
  que consultan la API real de datos.gov.co (`test_integration.py`,
  `test_secop_source.py`, `test_acceptance.py`), que fallan de forma
  intermitente por red. Ante un rojo, reintenta esa prueba sola antes de
  darla por regresión.
```

---

## Decisiones tomadas

- **El simulador no se pierde.** Rama `simulador`, creada antes de retirarlo de
  `frontend` y publicada en `origin/simulador`.
- **`main` no se toca.** Ningún prompt escribe en `main`.
- **No habrá rama `monitoreo`** (decisión del 2026-09-16). El plan original la
  contemplaba; se descarta. El Monitoreo en Vivo se queda como módulo de
  `frontend`, restringido al rol admin. Las ramas del proyecto son tres:
  `main`, `frontend` y `simulador`.
- **La paleta de `design.md` se usa tal cual** (decisión del 2026-09-16). Sus
  valores hex son una propuesta normalizada, no los colores reales de
  Plataforma50, que no pudieron leerse del sitio. Se asume el coste: si más
  adelante aparecen los reales, hay que rehacer el color. Como todo vive en
  `:root`, rehacerlo es un remapeo, no una reescritura.

## Pendiente (sin bloquear el Prompt 2)

- **Recortar la rama `simulador`.** Hoy es una copia completa de `frontend` en
  su estado previo. Cuando convenga, dejar solo el simulador y aplicarle los
  tokens ya migrados.
