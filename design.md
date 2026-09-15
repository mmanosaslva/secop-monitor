# Plataforma50 — Sistema de diseño

Fuente: https://www.plataforma50.com/ (home, ES-CO)
Extraído: 2026-09-15

> Nota sobre color: el sitio es un Next.js con hojas de estilo compiladas que no
> pudieron leerse desde aquí. Los valores hex de abajo son una **propuesta
> normalizada** a partir de la estructura y el tono del sitio (superficie oscura,
> un solo acento, mucho neutro). Si me pasas los hex reales —o una captura— los
> reemplazo y el resto del documento queda intacto.

---

## 1. Filosofía

**Premisa central:** "Convertimos procesos lentos en procesos inteligentes."

La marca no vende tecnología, vende **quitar fricción**. Todo el discurso parte
del dolor operativo del dueño de una empresa mediana que sigue operando en
manual, y termina en una operación que corre sola.

Cuatro principios que se repiten en cada sección:

1. **Diagnóstico antes de solución.** La entrada al negocio no es una propuesta,
   es una sesión gratis donde se busca la fricción. "Si algo de esto te suena, no
   es falta de esfuerzo: es falta de sistema."
2. **Antes / Ahora.** La estructura argumental dominante es la comparación
   pareada: Operación, Decisiones, Tiempo, Visibilidad. Papeles → una sola
   pantalla. Nunca se describe una capacidad sin su estado previo.
3. **Resultados medibles, no promesas.** Cada caso lleva un delta numérico
   explícito: 6 h → 25 min, 5 días → hoy, 80 %.
4. **Integrar, no reemplazar.** "No. Nos integramos con lo que ya tienes."
   La tecnología existente del cliente es punto de partida, no obstáculo.

**Postura:** consultor cercano, no proveedor. Trato de "tú", cero jerga
corporativa, la promesa siempre acotada ("Sin costo y sin compromiso").

---

## 2. Voz y copy

| Rasgo | Cómo se aplica |
|---|---|
| Persona | Segunda persona singular ("tú", "tu empresa", "tu equipo") |
| Nosotros | Primera del plural, verbo de acción: *entramos, conectamos, identificamos, capacitamos* |
| Longitud | Titular de 4–8 palabras + bajada de 1–2 frases. Nunca párrafos largos |
| Concreción | Nombres propios de herramientas reales: Excel, WhatsApp, Siigo, Shopify, Slack, Hikvision, n8n |
| Cierre | Siempre un CTA de conversación (WhatsApp), nunca "solicitar cotización" |
| Prohibido | Superlativos vacíos, "soluciones innovadoras", promesas sin número |

**Patrón de titular:** enunciado partido en dos líneas con quiebre semántico.

- "Convertimos procesos lentos / en procesos inteligentes"
- "Cada proceso, / con propósito."
- "Resultados, / no promesas."
- "Del caos en papeles / al control total de tu operación."

**Eyebrow (kicker) sobre cada titular:** una o dos palabras en minúscula o
sentence case — *El problema · Antes vs. ahora · Servicios · Casos de éxito ·
Conoce al experto · Lo último · Preguntas frecuentes*.

---

## 3. Color (propuesta normalizada)

Base oscura, un único acento, neutros de apoyo. Máximo dos fondos en toda la
pieza.

| Token | Valor | Uso |
|---|---|---|
| `--p50-ink` | `#0B0E14` | Fondo principal, secciones hero y footer |
| `--p50-surface` | `#13171F` | Tarjetas, filas de comparación, acordeón FAQ |
| `--p50-line` | `#232833` | Bordes de 1 px, separadores, contorno de chips |
| `--p50-text` | `#F4F6F8` | Texto principal sobre oscuro |
| `--p50-text-muted` | `#9AA3B2` | Bajadas, metadatos, labels |
| `--p50-accent` | `#2F6BFF` | CTA, numerales `[01]`, subrayados, estado "Ahora" |
| `--p50-accent-soft` | `#1B2A4D` | Fondo de badge, relleno de chip activo |
| `--p50-paper` | `#FFFFFF` | Secciones claras alternas (aliados, noticias) |
| `--p50-paper-ink` | `#0B0E14` | Texto sobre claro |

Reglas:

- Un solo acento por pantalla. El acento marca **acción** (CTA) y **estado
  deseado** (columna "Ahora"); el estado "Antes" va en neutro apagado.
- Cero degradados decorativos. El único recurso de fondo es media real: el
  `hero.webm` y `bg.webp`.
- Contraste mínimo 4.5:1 para texto; el `text-muted` solo sobre `ink`/`surface`.

---

## 4. Tipografía

Sistema de dos pesos sobre una sola familia sans geométrica-neutra (el sitio usa
una sans de una sola familia con contraste fuerte de tamaño, no de fuente).

| Rol | Tamaño / peso | Notas |
|---|---|---|
| Hero | 64–96 px, 600, `line-height: 1.02`, `letter-spacing: -0.03em` | Dos líneas, quiebre manual |
| Titular de sección | 40–56 px, 600, `-0.02em` | Punto final incluido |
| Eyebrow | 13–14 px, 500, `+0.08em`, uppercase o sentence case | Siempre sobre el titular |
| Subtítulo de tarjeta | 20–24 px, 600 | |
| Cuerpo | 16–18 px, 400, `line-height: 1.6` | Máx. 65 caracteres por línea |
| Dato / delta | 32–48 px, 600, tabular | "6 h → 25 min" |
| Meta / label | 12–13 px, 500, `+0.06em`, muted | "Destacado", "Experto líder" |
| Numeral | 13 px, mono o tabular, entre corchetes | `[01]` `[02]` |

`text-wrap: pretty` en toda bajada.

---

## 5. Layout y ritmo

- **Rejilla:** 12 columnas, ancho máximo de contenido ~1280 px, gutter 24–32 px.
- **Ritmo vertical:** secciones de 120–160 px de padding; nunca dos secciones
  seguidas con el mismo tratamiento de fondo.
- **Secuencia de la home** (usar como plantilla narrativa):
  1. Hero con video + CTA único + indicador "Scroll"
  2. Problema — 4 tarjetas numeradas `[01]`–`[04]`
  3. Antes vs. ahora — tabla de 4 filas, 2 columnas
  4. Beneficios — par de imágenes antes/ahora + tabs (Automatización, IA
     aplicada, A medida, Dashboards, Metodología)
  5. Servicios — lista numerada 01–05, la primera con badge "Destacado"
  6. Casos de éxito — 3 tarjetas con delta numérico + tags de servicio
  7. Experto líder — retrato + tres bloques (Lo que revisamos / encuentras /
     llevas) + credenciales + contadores (+10, +85)
  8. Equipo — 5 retratos cuadrados con enlace a LinkedIn
  9. Chips de posicionamiento — `[ Consultoría estratégica ]`, etc.
  10. Aliados — marquee de logotipos monocromos + contador
  11. Noticias — una entrada destacada
  12. FAQ — acordeón de 6 preguntas
  13. Footer — navegación en columnas, datos de contacto, CTA final grande

- **Elemento recurrente:** la dupla "Antes / Ahora" aparece en tres formatos
  distintos (tabla, par de imágenes, tarjeta de caso). Es el motivo visual de la
  marca.

---

## 6. Componentes

- **Botón primario:** pill o rect de radio 8–12 px, fondo acento, texto blanco,
  label de acción completa ("Agendar diagnóstico gratis"). Debajo, microcopy
  legal-tranquilizador en 13 px muted: "Sin costo y sin compromiso."
- **Tarjeta numerada:** numeral entre corchetes arriba, título 22 px, cuerpo
  muted, borde 1 px `--p50-line`, sin sombra.
- **Fila de comparación:** label a la izquierda, "Antes" en neutro, "Ahora" en
  acento; separador de 1 px entre filas.
- **Tarjeta de caso:** sector (meta) → delta numérico grande → título → antes →
  ahora → tags de servicio.
- **Chip / tag:** texto entre corchetes o pill de borde 1 px, 13 px, muted.
- **Acordeón FAQ:** pregunta 20 px, `+` o chevron a la derecha, respuesta 17 px
  muted, divisor de 1 px.
- **Marquee de aliados:** logotipos a una sola tinta, altura uniforme, opacidad
  ~0.7 → 1 en hover.
- **Contador animado:** número que cuenta desde 0 (`0+ aliados`, `+85 empresas`).

---

## 7. Fotografía e imagen

- Retratos de equipo: recorte cuadrado, fondo consistente, mismo encuadre.
- Ilustración de producto: capturas/renders de tableros y flujos reales, no
  vectores genéricos.
- Par antes/después: dos imágenes del mismo tamaño, una de desorden físico
  (papeles, notas) y una de pantalla ordenada. Es la imagen firma de la marca.
- Hero: video en loop, sin audio, oscurecido para que el titular conserve
  contraste.

---

## 8. Datos de la organización

- Plataforma50 — Barranquilla, Atlántico, Colombia
- Fundador y consultor estratégico: Santiago Campbell
- Contacto: +57 301 755 7782 · ceo@plataforma50.com · todos los días, 24 horas
- Canal primario de conversión: WhatsApp con mensaje prellenado por servicio
- Servicios: Automatización de procesos · IA & Machine Learning · Software a la
  medida · Dashboards & BI · Integraciones & APIs
- Prueba social: +85 empresas acompañadas, +10 años, 21 aliados institucionales
  (Alcaldía de Barranquilla, Cámara de Comercio de Bogotá y Barranquilla,
  Icontec, Colsubsidio, iNNpulsa, Gobernación del Atlántico, Universidad Libre…)
