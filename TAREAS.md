# Plan de trabajo — roles, permisos y rediseño

Rama base: `frontend`. Rama nueva al final: `monitoreo`.

**Orden: primero la funcionalidad (Fases 0-6, completadas), después el diseño
(Fases 7-9).**

Los prompts para ejecutar cada bloque están en [`prompts.md`](./prompts.md).

| Bloque | Fases | Prompt | Estado |
|--------|-------|--------|--------|
| Funcionalidad | 0 → 6 | Prompt 1 | **Completado** |
| Diseño y cierre | 7 → 9 | Prompt 2 | Siguiente |

**Ramas (son tres):** `main` intocable, sin la interfaz web · `frontend` rama de
trabajo · `simulador` archivo del módulo retirado.

> No hay ni habrá rama `monitoreo`: el plan original la contemplaba y se
> descartó el 2026-09-16. El Monitoreo en Vivo es un módulo de `frontend`,
> restringido al rol admin.

---

# BLOQUE A — Funcionalidad

## Fase 0 — Preparación

> **Fase 0 cerrada el 2026-09-15** sobre el commit `d343f87`.

- [x] 0.1 `frontend` limpia y sincronizada (`Already up to date`).
- [x] 0.2 `pytest`: **53 pasan, 0 fallos**. Estado inicial VERDE.
      Ejecutar con el entorno del proyecto: `./.venv/bin/python -m pytest -q`
      (el python del sistema no tiene pytest instalado).
      Ruido conocido: 12 warnings por marcas sin registrar (`acceptance`,
      `integration`, `slow`); no son fallos.
- [x] 0.3 Servidor verificado (`PORT=8099 ./.venv/bin/python src/web_server.py`):
      `/` 27656 B, `/styles.css` 21328 B, `/app.js` 24173 B, todos HTTP 200.
      `/api/config` y `/api/secop/live` responden 200.
      **Referencia de la UI inicial — 6 tabs:** `dashboard`, `architecture`,
      `secop-live`, `simulator`, `config`, `email-preview`.
      Título actual: `SECOP Monitor - Servicio Nacional de Aprendizaje SENA`.
      Al terminar el Prompt 1 deben quedar 4 (sin `simulator` ni `email-preview`,
      que pasa a ser desplegable).
- [x] 0.4 **Preservar el simulador antes de borrarlo:** rama `simulador` creada
      desde `frontend` (`git branch simulador frontend`). Verificado que conserva
      `#tab-simulator`, `initSimulator()` y `runSimulation()`.
- [x] 0.5 Upstream de `frontend` corregido: apuntaba a `origin/main`, ahora sigue
      a `origin/frontend`. Protege la regla de no tocar `main`.
- [x] 0.6 Rama `simulador` publicada en el remoto (`origin/simulador`). Es un
      archivo, no se fusiona: ignorar la invitación de GitHub a abrir un PR.

## Fase 1 — Base de roles

> **Cerrada.** Commit `6d0c289`. Sesiones con cookie HttpOnly, mapa PERMISOS
> en el backend y `puede()` en el frontend. 20 pruebas.

- [x] 1.1 Definir el modelo de usuario (id, nombre, correo, rol, estado, último acceso).
- [x] 1.2 Pantalla de acceso que fija el rol de la sesión (`admin` / `usuario`).
- [x] 1.3 Persistir el rol en la sesión del navegador y exponerlo a `app.js`.
- [x] 1.4 Función central `puede(accion)` que resuelva permisos en un solo lugar.
- [x] 1.5 Commit: `feat: sistema de roles admin y usuario`.

## Fase 2 — Permisos en la navegación

> **Cerrada.** Commit `391545d`. El nav se construye desde el registro MODULOS;
> lo no autorizado no llega al DOM. Vista de acceso denegado incluida.

- [x] 2.1 Renderizar el nav según el rol, no ocultar con CSS.
- [x] 2.2 Rol `usuario`: solo **Panel de Métricas** y **¿Cómo Funciona por Dentro?**.
- [x] 2.3 Rol `admin`: lo anterior + **Monitoreo en Vivo** + **Configuración del Cliente**
      + **Gestión de Usuarios**.
- [x] 2.4 Vista de acceso denegado al intentar entrar a un tab no autorizado.
- [x] 2.5 Commit: `feat: navegacion condicionada por rol`.

## Fase 3 — Métricas de solo lectura para `usuario`

> **Cerrada.** Commit `6948222`. Nuevos `/api/metrics` y `/api/sync`. Se cerró
> un agujero: el frontend consultaba datos.gov.co directamente cuando la API
> devolvía error, saltándose el 403 del backend. 7 pruebas.

- [x] 3.1 Quitar del render de `usuario` todo control de escritura (guardar,
      editar, sincronización manual — ver `initManualSync()` en `app.js:454`).
- [x] 3.2 Dejar los mismos controles activos para `admin`.
- [x] 3.3 Bloquear en `src/web_server.py` los `do_POST` (`/api/config`,
      `/api/filter/test`) cuando el rol no es `admin`.
- [x] 3.4 Tests de permisos del backend (rol no autorizado → rechazo).
- [x] 3.5 Commit: `feat: metricas de solo lectura para rol usuario`.

## Fase 4 — Notificaciones como desplegable

> **Cerrada.** Commit `b39d592`. Campana con badge en el encabezado.
> `initEmailPreview()` sobrevive como `construirCorreoHtml()`. 7 pruebas.

- [x] 4.1 Eliminar el tab "Notificación Brevo" (`index.html:69`) y la sección
      `#tab-email-preview` (`index.html:504-528`).
- [x] 4.2 Añadir campana con badge de conteo en el header.
- [x] 4.3 Panel flotante: lista de notificaciones, leída/no leída, estado vacío,
      cierre al hacer clic fuera.
- [x] 4.4 Reutilizar la lógica de `initEmailPreview()` (`app.js:353`) que siga siendo útil.
- [x] 4.5 Disponible para ambos roles.
- [x] 4.6 Commit: `feat: notificaciones como desplegable en el header`.

## Fase 5 — Gestión y control de usuarios (solo `admin`)

> **Cerrada.** Commit `532fe56`. CRUD completo con salvaguardas de autobloqueo
> y de último administrador. 17 pruebas.

- [x] 5.1 Nuevo módulo "Gestión de Usuarios" visible solo para `admin`.
- [x] 5.2 Tabla de usuarios: avatar, nombre, correo, rol, estado, último acceso.
- [x] 5.3 Acciones: crear, editar, activar/desactivar, cambiar rol.
- [x] 5.4 Métricas agregadas de uso por usuario (accesos, acciones, estado).
- [x] 5.5 Endpoints de backend para el CRUD, protegidos por rol.
- [x] 5.6 Tests del CRUD y de su protección por rol.
- [x] 5.7 Commit: `feat: panel de gestion y metricas de usuarios para admin`.

## Fase 6 — Retirar el simulador y cerrar la funcionalidad

> **Cerrada.** Commit `cd61f88`. Verificada antes la rama `simulador`.

> El módulo está a salvo en la rama `simulador`. Antes de borrar, confirmar:
> `git grep -c 'tab-simulator' simulador -- src/web/index.html`

- [x] 6.0 Verificar que la rama `simulador` conserva el módulo.
- [x] 6.1 Quitar el tab "Simulador del Motor" (`index.html:63`).
- [x] 6.2 Quitar la sección `#tab-simulator` (`index.html:379-449`).
- [x] 6.3 Quitar `initSimulator()` (`app.js:277`) y `runSimulation()` (`app.js:284`).
- [x] 6.4 Quitar los estilos asociados en `styles.css`.
- [x] 6.5 Verificar que no queden referencias muertas (`grep -rn simulator src/web`).
- [x] 6.6 Commit: `refactor: eliminar el simulador del motor de la interfaz`.
- [x] 6.7 **Puerta de calidad:** `pytest` en verde y prueba manual de los dos roles
      de punta a punta. No se pasa al bloque de diseño sin esto.
- [x] 6.8 **Puerta de estilos (corregida).** La afirmación inicial de que
      `styles.css` estaba totalmente tokenizado era **falsa**: solo se había
      buscado los dos colores SENA, no todos los hexadecimales. Al empezar había
      **28** colores en duro fuera de `:root`. Retirar el previsualizador de
      correo y el simulador dejó **16**. Todo el CSS nuevo de estas fases usa
      variables, cero hexadecimales.
      Verificación: `awk '/^:root/{r=1} r&&/^}/{r=0;next} !r' src/web/styles.css | grep -cE '#[0-9A-Fa-f]{3,8}'`

---

# BLOQUE B — Diseño (al final, sobre la estructura ya terminada)

> **Stack:** `design.md` es la fuente de verdad → la skill `design` de Claude Code
> genera el canvas → el Artifact publicado permite editarlo visualmente → los
> tokens aterrizan en `:root` de `src/web/styles.css`.
> No hay MCP de Claude Design; la integración es la skill.

## Fase 7 — Canvas de diseño (Claude Design)

> **Canvas A entregado y aprobado (2026-09-16).** 7 artboards: tokens, acceso
> (1440 + 390) con sus tres estados de error, métricas USUARIO (1440 + 390),
> métricas ADMIN y estados transversales.
> Fuentes en `design/canvas-a/*.dc.html`; el lienzo sembrado se regenera desde
> ahí y no se versiona.
> Decisiones: logotipo provisional (falta la marca real), Archivo + JetBrains
> Mono como familias, y dos colores fuera de la paleta (rojo y ámbar apagados)
> reservados a error y aviso.

- [x] 7.1 Releer `design.md` completo (181 líneas) antes de generar nada.
- [x] 7.2 **Canvas A — núcleo:** tira de tokens + Login/selección de rol +
      Métricas rol USUARIO + Métricas rol ADMIN + estados transversales
      (nav por rol, vacío, carga, acceso denegado).
- [x] 7.3 Revisar y aprobar el Canvas A. Los tokens que salgan de aquí son los
      que rigen el Canvas B.
- [ ] 7.4 **Canvas B — módulos:** ¿Cómo Funciona por Dentro? (motivo "Antes/Ahora")
      + Desplegable de Notificaciones + Gestión de Usuarios + Configuración del
      Cliente + Monitoreo en Vivo.
- [ ] 7.5 Variantes móviles de 390px para login, métricas de usuario y
      desplegable de notificaciones. Desktop a 1440px.
- [ ] 7.6 Verificar que ningún artboard incluye el Simulador del Motor.
- [ ] 7.7 Revisar y aprobar el Canvas B.

## Fase 8 — Implementación del diseño en código

- [ ] 8.1 Sustituir el bloque `:root` de `src/web/styles.css`: `--sena-green`,
      `--sena-navy`, `--bg-*`, `--text-*`, `--border-*` pasan a los tokens
      Plataforma50 (`--p50-ink`, `--p50-surface`, `--p50-line`, `--p50-text`,
      `--p50-text-muted`, `--p50-accent`, `--p50-accent-soft`, `--p50-paper`).
- [ ] 8.2 Corregir `--border-focus` (`styles.css:23`), que hoy repite el verde
      SENA en duro en lugar de referenciar una variable.
- [ ] 8.3 Ajustar la escala tipográfica (titular 40-56px/600/-0.02em, eyebrow
      13-14px/+0.08em, cuerpo 16-18px/1.6, dato 32-48px tabular, numeral `[01]` mono).
- [ ] 8.4 Eliminar sombras (`--shadow-*`) y degradados decorativos; bordes de 1px.
- [ ] 8.5 Un solo acento por pantalla: revisar que no queden dos colores compitiendo.
- [ ] 8.6 Eliminar "SECOP II Monitor" del header (`index.html:31`, el
      `<h1 class="app-title">` con el `<span class="tag-v2">`).
- [ ] 8.7 Eliminar el bloque "SECOP Monitor v2.0" del footer (`index.html:529-535`),
      conservando la descripción funcional y la línea institucional.
- [ ] 8.8 Aplicar la voz y el copy de §2 de `design.md` (segunda persona, eyebrow
      en minúscula, titulares de 4-8 palabras, cada dato con número explícito).
- [ ] 8.9 Revisar contraste mínimo 4.5:1 en todo texto.
- [ ] 8.10 Commit: `estilo: migrar interfaz al sistema de diseño Plataforma50`.

## Fase 9 — Cierre de `frontend`

- [ ] 9.1 `pytest` en verde.
- [ ] 9.2 Prueba manual de los dos roles de punta a punta, ya con el diseño aplicado.
- [ ] 9.3 Push de `frontend` y PR hacia `main`.

---

## Decisiones tomadas

- **El simulador no se pierde:** rama `simulador`, creada antes de retirarlo.
- **No habrá rama `monitoreo`** (2026-09-16). El Monitoreo en Vivo es un módulo
  de `frontend`, solo para admin.
- **`main` no se toca en ninguna fase.** Verificado que no contiene `src/web/`,
  así que tampoco sirve como respaldo de la interfaz.
- **La paleta de `design.md` se usa tal cual** (2026-09-16), asumiendo que sus
  hex son una propuesta y no los colores reales de Plataforma50.
