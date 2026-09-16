# Prompts de trabajo — mvp_SECOP

Tres prompts listos para copiar y pegar. El plan de ejecución paso a paso está en
[`TAREAS.md`](./TAREAS.md).

**Orden de trabajo: primero la funcionalidad, el diseño al final.**

| # | Prompt | Rama | Qué entrega |
|---|--------|------|-------------|
| 1 | Roles, permisos y limpieza | `frontend` | Funcionalidad completa sobre la UI actual |
| 2 | Diseño visual Plataforma50 | `frontend` | Canvas en Claude Design + migración en código |
| 3 | Rama de monitoreo | `monitoreo` | Derivación con solo monitoreo en vivo |

### Mapa de ramas

| Rama | Contenido | Estado |
|------|-----------|--------|
| `main` | Motor, tests y config. **No contiene la interfaz web** | **INTOCABLE** — no se modifica sin orden explícita |
| `frontend` | Producto: roles, métricas, notificaciones, gestión de usuarios | Rama de trabajo |
| `simulador` | Simulador del Motor, preservado íntegro | **Ya creada** (rescate previo a la limpieza) |
| `monitoreo` | Solo Monitoreo en Vivo SECOP II | Se deriva en el Prompt 3 |

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
3. **`monitoreo` hereda el diseño gratis.** Al crear la rama *después* del
   rediseño, no hay que aplicar `design.md` dos veces ni arriesgar que las dos
   ramas diverjan visualmente.

> **Nota sobre el orden de la rama `monitoreo`:** queda *después* del diseño
> precisamente por el punto 3. Si prefieres crearla antes, hay que aceptar
> aplicar `design.md` por separado en cada rama.

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

## Prompt 2 — Diseño visual Plataforma50 (rama `frontend`, después del Prompt 1)

```
Diseña el sistema visual completo del aplicativo web SECOP Monitor siguiendo
ESTRICTAMENTE el sistema de diseño documentado en `design.md` (rama `frontend`),
y después impleméntalo en código.

CONTEXTO
- El Prompt 1 ya está aplicado: existen los dos roles, el nav condicionado, las
  notificaciones como desplegable y la gestión de usuarios. El simulador ya no
  existe. Diseña sobre esa estructura, no sobre la anterior.
- El código está en `src/web/index.html`, `src/web/styles.css`, `src/web/app.js`.
- La interfaz usa estilo institucional SENA (verde #39A900, azul #00324D,
  Montserrat). Debe migrar al sistema Plataforma50 de `design.md`.

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
2. ELIMINA el nombre "SECOP II Monitor" del header y del footer. El header no
   lleva wordmark de texto: solo el logotipo/marca, las píldoras de estado del
   sistema y los controles de usuario. El footer queda sin el bloque
   "SECOP Monitor v2.0"; conserva únicamente la descripción funcional y la línea
   institucional.
3. Voz y copy según §2 de `design.md`: segunda persona, titulares de 4-8
   palabras partidos en dos líneas, eyebrow en minúscula sobre cada titular,
   nada de superlativos vacíos, cada dato con número explícito.

ENTREGA EN DOS CANVAS (no todo en uno: 14 artboards en una pasada degradan los
últimos)

CANVAS A — núcleo del sistema
  0. Tira superior de tokens: paleta, escala tipográfica, botones, chip, tarjeta
     numerada, fila de comparación, acordeón.
  1. *Login / selección de rol — CTA único, microcopy tranquilizador debajo.
  2. *Panel de Métricas — rol USUARIO (solo lectura): KPIs en tarjetas numeradas
     `[01]`-`[04]`, sin ningún control de edición ni botones de guardar.
  3. Panel de Métricas — rol ADMIN: mismos KPIs + controles de edición visibles.
  4. Estados transversales: barra de navegación en ambos roles (el nav de USUARIO
     solo muestra Métricas y ¿Cómo Funciona por Dentro?), estado vacío, estado de
     carga, y mensaje de acceso denegado.

CANVAS B — módulos (reutiliza los tokens ya fijados en el Canvas A)
  5. ¿Cómo Funciona por Dentro? — narrativa del motor usando el motivo de marca
     "Antes / Ahora" (fila de comparación: label izquierda, "Antes" en neutro
     apagado, "Ahora" en acento).
  6. *Desplegable de Notificaciones — campana en el header con badge de conteo,
     panel flotante con lista de notificaciones (leída / no leída), estado vacío
     y enlace "ver todas". NO es una página ni un módulo del nav.
  7. Gestión de Usuarios — solo ADMIN: tabla de usuarios (avatar, nombre, correo,
     rol, estado, último acceso), acciones por fila, métricas agregadas de uso
     arriba, modal de crear/editar usuario.
  8. Configuración del Cliente — solo ADMIN.
  9. Monitoreo en Vivo — pantalla independiente: tabla de procesos SECOP II con
     buscador, filtro por departamento, filtro por coincidencia y modal de detalle.

Los marcados * llevan además variante móvil de 390px. Desktop a 1440px.
Artboards ordenados por flujo dentro de cada canvas.

NO incluyas en ningún artboard el módulo "Simulador del Motor": ya fue eliminado.

IMPLEMENTACIÓN EN CÓDIGO (después de aprobados los dos canvas)
- Sustituye el bloque `:root` de `src/web/styles.css`: los tokens `--sena-*`
  pasan a `--p50-*`. Además quedan 16 colores en duro fuera de `:root` que hay
  que convertir a variables; localízalos con
  `awk '/^:root/{r=1} r&&/^}/{r=0;next} !r' src/web/styles.css | grep -nE '#[0-9A-Fa-f]{3,8}'`.
- Ajusta la escala tipográfica, quita sombras y degradados, deja bordes de 1px.
- Aplica la regla 2 (nombre fuera de header y footer) en `index.html`.
- Verifica contraste 4.5:1 en todo texto.
```

---

## Prompt 3 — Rama `monitoreo` (a partir de `frontend` ya funcional y rediseñada)

```
Crea la rama `monitoreo` a partir de `frontend`, con los Prompts 1 y 2 ya
aplicados (funcionalidad completa y diseño Plataforma50 migrado).

- En esa rama deja SOLO la funcionalidad de monitoreo en vivo: el tab
  "Monitoreo en Vivo (SECOP II)" (`#tab-secop-live`), su tabla, filtros,
  modal de detalle, `initLiveSECOP()` / `loadLiveSecopData()` y el endpoint
  `/api/secop/live`. Elimina de esa rama el resto de módulos, su JS y su CSS.
- El sistema de diseño de `design.md` ya viene heredado de `frontend`: NO hay que
  volver a aplicarlo, solo verificar que la pantalla resultante lo respeta y que
  no queda CSS huérfano de los módulos eliminados.
- Verifica que la rama arranca y consulta SECOP II de forma autónoma.
```

---

## Decisiones tomadas

- **El simulador no se pierde.** Se creó la rama `simulador` a partir de
  `frontend` antes de empezar cualquier trabajo. Conserva el módulo íntegro y
  funcional. El Prompt 1 lo retira de `frontend` con esa red ya puesta.
- **`monitoreo` queda solo con monitoreo en vivo.** El simulador no se traslada
  allí: tiene su propia rama.
- **`main` no se toca.** Ninguno de los tres prompts escribe en `main`.

## Pendiente (sin bloquear el Prompt 1)

- **Recortar la rama `simulador`.** Hoy es una copia completa de `frontend`. En
  algún momento conviene dejar en ella solo el simulador y aplicarle los tokens
  Plataforma50 (copiar el bloque `:root` ya migrado). Es barato gracias a la
  tokenización del CSS, y puede hacerse en cualquier momento posterior.
- **Corregir el upstream de `frontend`.** Apunta a `origin/main` en lugar de a
  `origin/frontend`. Arreglo: `git branch -u origin/frontend frontend`.
