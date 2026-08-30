# SECOP Monitor MVP

Sistema de monitoreo automatico de oportunidades de contratacion publica en SECOP II. Detecta procesos relevantes, los almacena en base de datos y envia notificaciones por correo electronico.

## Arquitectura

```
GitHub Actions (3x/dia: 10:00, 15:00, 20:00 COT)
        |
        v
Python Script (src/main.py)
        |
        +--> SECOP Source (datos.gov.co SODA API)
        |
        +--> Filter Engine (keywords + UNSPSC + ubicacion)
        |
        +--> PostgreSQL (Neon) -- persistencia
        |
        +--> Email Notification (Brevo API)
```

## Stack

| Componente | Tecnologia | Costo |
|---|---|---|
| Runtime | Python 3.11+ | $0 |
| Base de datos | Neon PostgreSQL | $0 (free tier) |
| Email | Brevo | $0 (free tier) |
| Hosting/Cron | GitHub Actions | $0 (free tier) |
| Fuente datos | SECOP / datos.gov.co | $0 (datos abiertos) |
| Codigo fuente | GitHub | $0 |

**Total: $0/mes**

---

## Costos y Servicios

### SECOP / datos.gov.co

- **Fuente:** `https://www.datos.gov.co/resource/p6dx-8zbt.json`
- **Costo:** Gratuito (datos abiertos, licencia CC BY-SA 4.0)
- **Actualizacion:** Diaria (~12:00-14:00 COT). Latencia: 1-2 dias
- **App Token:** Opcional. Registro gratuito para mejorar limites

### Neon (PostgreSQL)

- **Plan:** Free
- **Storage:** 0.5 GB por proyecto
- **Compute:** 100 CU-hours/mes
- **Scale-to-zero:** Si, despues de 5 minutos de inactividad
- **Cold start:** ~300-500ms
- **Region recomendada:** aws-sa-east-1 (Sao Paulo, cercana a Colombia)

### Brevo (Email)

- **Plan:** Free
- **Limite:** 300 emails/dia (~9,000/mes)
- **Remitente:** Requiere verificacion de dominio (SPF/DKIM)
- **Limites:** Marca de agua Brevo en emails gratuitos

### GitHub Actions (Cron)

- **Plan:** Free (2000 min/mes para repos privados)
- **Ejecucion:** 3 veces al dia = ~15 min/mes
- **Limitos:** 1000 ejecuciones/dia, 6 horas max por ejecucion

### WhatsApp (Funcionalidad Futura)

**Estado:** Actualmente el sistema envia notificaciones por correo electronico. WhatsApp esta disenado como una mejora futura.

**Como funciona WhatsApp Business?**

Para enviar mensajes de WhatsApp de forma automatizada, se necesita:

1. **Cuenta de Meta Business Manager** (gratis) - Registro en business.facebook.com
2. **Numero de telefono verificado** - Puede ser el numero actual del negocio
3. **Verificacion de negocio** - Meta verifica la identidad del negocio (tarda 1-5 dias)
4. **Plantillas de mensajes** - Los mensajes deben ser aprobados por Meta antes de enviarlos

**Costo estimado:**
- Cada mensaje de WhatsApp cuesta aproximadamente $20 COP
- Con 36 notificaciones diarias, el costo mensual seria ~$21,600 COP (~$5 USD)

**Por que no esta implementado todavia?**
- Requiere verificacion de negocio (1-5 dias)
- Cada mensaje tiene costo (a diferencia del correo que es gratis)
- Para el MVP actual, el correo electronico es suficiente

**Configuracion necesaria:**
```json
{
  "phone_whatsapp": "+57XXXXXXXXXX",
  "whatsapp_enabled": true
}
```

---

## Como Ejecutar

### Ejecucion Local

```bash
# 1. Clonar repositorio
git clone https://github.com/mmanoslasva/secop-monitor.git
cd secop-monitor

# 2. Crear entorno virtual
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
# Editar .env con tus credenciales

# 5. Ejecutar
python -m src.main
```

### Ejecucion en GitHub Actions (Produccion)

El cron esta configurado en `.github/workflows/secop.yml`:

```yaml
schedule:
  - cron: '0 15 * * *'  # 10:00 AM COT
  - cron: '0 20 * * *'  # 3:00 PM COT
  - cron: '0 1 * * *'   # 8:00 PM COT
```

**Ejecucion manual:**
1. Ir al repositorio en GitHub
2. Pestaña "Actions"
3. Seleccionar "SECOP Monitor"
4. Click "Run workflow"

**Verificar ejecucion:**
1. En la pestaña "Actions", click en la ejecucion
2. Ver logs de cada paso
3. Verificar en Neon: tablas `job_runs`, `processes`, `notifications`

### Variables de Entorno

| Variable | Descripcion | Ejemplo |
|----------|-------------|---------|
| `DATABASE_URL` | URL de conexion a Neon | `postgresql://user:pass@ep-xxx.neon.tech/neondb?sslmode=require` |
| `BREVO_API_KEY` | API key de Brevo | `xkeysib-...` |
| `SENDER_EMAIL` | Email remitente verificado | `whoami_jay@proton.me` |
| `SENDER_NAME` | Nombre del remitente | `SECOP Monitor` |
| `ADMIN_EMAIL` | Email del administrador | `meriyei.manfer@gmail.com` |
| `STEALTH_MODE` | `true` = sin envio, `false` = envio real | `false` |

---

## Configuracion del Cliente

Archivo `config/client_config.json`:

```json
{
  "name": "Cliente Textil Caribe",
  "email": "meriyei.manfer@gmail.com",
  "phone_whatsapp": "+573001234567",
  "departments": ["Atlantico", "Bolivar", "Magdalena", "Cordoba", "Sucre", "La Guajira", "Cesar"],
  "keywords": ["uniforme", "uniformes", "ropa deportiva", "vestuario", "confeccion", "prendas", "textil", "sportswear", "camiseta", "pantalon", "chaqueta", "calzado"],
  "unspsc_codes": ["V1.53102700", "V1.53102710", "V1.53102715", "V1.53102720", "V1.53102900", "V1.53102901", "V1.53102902", "V1.53100000", "V1.53101500", "V1.53101600", "V1.53101800", "V1.53103000", "V1.53110000", "V1.53111600"]
}
```

### Logica de Filtrado

Un proceso se notifica si:
1. Su departamento esta en la lista, Y
2. Cumple AL MENOS UNO:
   - Su codigo UNSPSC esta en la lista
   - Su nombre o descripcion contiene una keyword

---

## Monitoring

### Consultas SQL Utiles

```sql
-- Ultima ejecucion
SELECT * FROM job_runs ORDER BY started_at DESC LIMIT 1;

-- Procesos detectados hoy
SELECT COUNT(*) FROM processes WHERE detected_at >= CURRENT_DATE;

-- Notificaciones fallidas
SELECT n.*, p.name
FROM notifications n
JOIN processes p ON n.process_id = p.id
WHERE n.status = 'failed' AND n.retry_count < 3;

-- Resumen ultima semana
SELECT
    DATE(detected_at) as day,
    COUNT(*) as detected,
    SUM(CASE WHEN notified THEN 1 ELSE 0 END) as notified
FROM processes
WHERE detected_at >= NOW() - INTERVAL '7 days'
GROUP BY DATE(detected_at)
ORDER BY day DESC;
```

---

## Estructura del Proyecto

```
secop-monitor/
├── .github/workflows/secop.yml   # Cron de GitHub Actions
├── config/client_config.json     # Configuracion del cliente
├── src/
│   ├── main.py                   # Punto de entrada
│   ├── config.py                 # Variables de entorno
│   ├── sources/secop.py          # Conexion con SECOP API
│   ├── filters/engine.py         # Motor de filtros
│   ├── database/connection.py    # Conexion a Neon
│   ├── database/models.py        # Operaciones CRUD
│   └── notifications/email.py    # Envio de correos via Brevo
├── tests/                        # Tests unitarios
├── Dockerfile                    # Para Docker (opcional)
├── requirements.txt              # Dependencias
├── .env.example                  # Ejemplo de variables
└── README.md                     # Esta documentacion
```

---

## Configuracion Dominio Propio en Brevo

### Por que llegan a spam?

Brevo free tier usa dominio compartido `brevosend.com`. Gmail ve ese dominio como remitente y clasifica como spam. Con dominio propio, los emails llegan desde `tudominio.com` → confianza → inbox.

### Pasos

1. **Comprar dominio** (~$10/año) - Namecheap, Cloudflare, Porkbun
2. **Verificar dominio en Brevo** - Agregar registros DNS (TXT, CNAME)
3. **Agregar registros en proveedor DNS** - Esperar propagacion (1-2 horas)
4. **Confirmar verificacion en Brevo** - Click "Verify"
5. **Configurar sender** - `notificaciones@tudominio.com`

### Resultado

| Antes | Despues |
|-------|---------|
| `whoami_jay@12002987.brevosend.com` | `notificaciones@tudominio.com` |
| 30-40% va a spam | <5% va a spam |
| Sin credibilidad | Dominio profesional |

---

## Funcionalidades Futuras

1. **WhatsApp** - Notificaciones via Meta Cloud API
2. **Multi-tenant** - Multiples clientes con diferentes filtros
3. **Dashboard** - Panel web para gestionar filtros y ver historial
4. **Deteccion de cambios** - Notificar actualizaciones a procesos existentes
5. **Filtro por valor** - Excluir procesos por monto
6. **Filtro por entidad** - Incluir/excluir entidades especificas
7. **Filtro por modalidad** - Licitacion publica, seleccion abreviada, etc.
8. **Filtro por fecha limite** - Excluir procesos vencidos

---

## Troubleshooting

| Error | Causa | Solucion |
|-------|-------|----------|
| `can't adapt type 'dict'` | Campo `urlproceso` devuelve dict | Verificar `secop.py` maneja dict |
| `ModuleNotFoundError` | Dependencias no instaladas | `pip install -r requirements.txt` |
| `connection timeout` | Neon en sleep mode | Esperar ~300ms, verificar URL |
| Emails van a spam | Dominio compartido Brevo | Configurar dominio propio |
| `email_failed status=401` | API key incorrecta | Verificar `BREVO_API_KEY` |
| `email_failed status=400` | Email no verificado | Verificar `SENDER_EMAIL` en Brevo |
| GitHub Actions no ejecuta | Cron puede tardar 15 min | Ejecutar manualmente via "Run workflow" |
