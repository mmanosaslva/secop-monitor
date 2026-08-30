# SECOP Monitor MVP

Sistema que detecta automaticamente oportunidades de contratacion publica en SECOP II relevantes para un cliente especifico y envia notificaciones por correo electronico.

## Arquitectura

```
GitHub Actions Cron (3x/dia: 10:00, 15:00, 20:00 COT)
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

## Costos y Servicios Externos

### SECOP / datos.gov.co

- **Fuente:** `https://www.datos.gov.co/resource/p6dx-8zbt.json`
- **Costo:** Gratuito (datos abiertos, licencia CC BY-SA 4.0)
- **Límites:** Rate limiting. App token gratuito mejora limits
- **Actualización:** Diaria (~12:00-14:00 COT). Latencia: 1-2 dias desde community.secop.gov.co
- **App Token:** Opcional. Registro gratuito en `https://www.datos.gov.co/profile/edit/developer_settings`

### Neon (PostgreSQL)

- **Plan:** Free
- **Storage:** 0.5 GB por proyecto
- **Compute:** 100 CU-hours/mes (~3.3 horas de 1 CU)
- **Scale-to-zero:** Si, despues de 5 minutos de inactividad
- **Cold start:** ~300-500ms
- **Limitos:** 10 ramas/proyecto, 5 GB egress/mes, sin SLA
- **Región recomendada:** aws-sa-east-1 (Sao Paulo, cercana a Colombia)
- **Cuándo genera costos:** Si se supera 0.5 GB storage o 100 CU-hours

### Brevo (Email)

- **Plan:** Free
- **Limite:** 300 emails/dia (~9,000/mes)
- **Remitente:** Requiere verificacion de dominio (SPF/DKIM)
- **Limites:** Marca de agua Brevo en emails gratuitos
- **SDK:** `pip install brevo-python`
- **Cuándo genera costos:** Al superar 300 emails/dia o al upgrade a Starter ($9/mes)

### GitHub Actions (Hosting/Cron)

- **Plan:** Free (2000 min/month para repos privados, ilimitado para public)
- **Cron jobs:** Nativo via `schedule` en workflows YAML
- **2000 minutos/mes** para repos privados (3 ejecuciones/dia = ~15 min/mes)
- **Deploy:** GitHub integration, auto-deploy on push
- **Limitos:** 1000 ejecuciones/dia, 6 horas max por ejecucion
- **Cuándo genera costos:** Si se supera 2000 min/mes (no aplica para nuestro caso)

### WhatsApp (Funcionalidad Futura - NO utilizada en MVP)

- **Estado:** No implementada en el MVP
- **Proveedor recomendado:** Meta WhatsApp Cloud API (directo, sin BSP)
- **Costo por mensaje (Colombia):** ~$0.005 USD/mensaje utility, ~$0.0125 USD/mensaje marketing
- **Costo plataforma:** $0 (Meta Cloud API directa)
- **Requisitos:** Meta Business Manager, verificacion de negocio (1-5 dias), registro de numero, plantillas aprobadas
- **Alternativa BSP:** 360dialog: EUR 49/mes sin markup
- **Nota:** investigar condiciones actuales de Meta cuando se implemente esta fase. Colombia tiene tarifas de las mas bajas mundialmente

---

## Setup

### 1. Crear cuenta Neon (PostgreSQL)

1. Ir a `https://neon.tech`
2. Crear cuenta (gratis, sin tarjeta)
3. Crear proyecto (region: aws-sa-east-1)
4. Copiar la `DATABASE_URL` que Neon te da

### 2. Crear tablas en Neon

En el SQL Editor de Neon, ejecutar:

```sql
CREATE TABLE processes (
    id TEXT PRIMARY KEY,
    entity_name TEXT,
    entity_nit TEXT,
    department TEXT,
    city TEXT,
    name TEXT,
    description TEXT,
    status TEXT,
    phase TEXT,
    contract_type TEXT,
    modality TEXT,
    base_price NUMERIC,
    publication_date TIMESTAMPTZ,
    deadline TIMESTAMPTZ,
    unspsc_code TEXT,
    url TEXT,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notified BOOLEAN DEFAULT FALSE,
    content_hash TEXT
);

CREATE TABLE notifications (
    id SERIAL PRIMARY KEY,
    process_id TEXT NOT NULL REFERENCES processes(id),
    channel TEXT NOT NULL CHECK (channel IN ('email', 'whatsapp')),
    status TEXT NOT NULL CHECK (status IN ('pending', 'sent', 'failed')),
    sent_at TIMESTAMPTZ,
    error_message TEXT,
    retry_count INT DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE job_runs (
    id SERIAL PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    status TEXT CHECK (status IN ('running', 'success', 'failed')),
    processes_found INT DEFAULT 0,
    processes_matched INT DEFAULT 0,
    notifications_sent INT DEFAULT 0,
    notifications_failed INT DEFAULT 0,
    error_message TEXT
);

CREATE TABLE client_config (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone_whatsapp TEXT,
    departments JSONB NOT NULL DEFAULT '[]',
    keywords JSONB NOT NULL DEFAULT '[]',
    unspsc_codes JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_processes_status ON processes(status);
CREATE INDEX idx_processes_department ON processes(department);
CREATE INDEX idx_processes_detected ON processes(detected_at);
CREATE INDEX idx_processes_notified ON processes(notified);
CREATE INDEX idx_notifications_process ON notifications(process_id);
CREATE INDEX idx_notifications_status ON notifications(status);
CREATE INDEX idx_job_runs_started ON job_runs(started_at);
```

### 3. Crear cuenta Brevo (Email)

1. Ir a `https://www.brevo.com`
2. Crear cuenta (gratis)
3. Ir a "Transactional Emails" > "Senders"
4. Agregar tu email de envio
5. Seguir instrucciones para verificar dominio (SPF/DKIM)
6. Copiar la API Key de Settings > API Keys

### 4. Crear cuenta GitHub y activar Actions

1. Ir a `https://github.com`
2. Crear cuenta (si no tienes)
3. Crear repositorio `secop-monitor`
4. Subir codigo (ver paso 1 en "Deploy a Produccion")
5. Ir a pestaña "Actions" en el repositorio
6. Click "I understand my workflows, go ahead and enable them"
7. Los cron jobs se ejecutaran automaticamente segun el schedule definido en `.github/workflows/secop.yml`

### 5. Variables de Entorno

```
DATABASE_URL=postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require
BREVO_API_KEY=your-brevo-api-key
SECOP_APP_TOKEN=your-socrata-app-token
SENDER_EMAIL=notificaciones@tudominio.com
SENDER_NAME=SECOP Monitor
ADMIN_EMAIL=admin@tudominio.com
STEALTH_MODE=true
```

---

## Configuracion del Cliente

Archivo `config/client_config.json`:

```json
{
  "name": "Cliente Textil Caribe",
  "email": "cliente@empresa.com",
  "departments": ["Atlantico", "Bolivar", "Magdalena", "Cordoba", "Sucre", "La Guajira", "Cesar"],
  "keywords": ["uniforme", "uniformes", "ropa deportiva", "vestuario", "confeccion", "prendas", "textil"],
  "unspsc_codes": ["V1.53102700", "V1.53102710", "V1.53102715", "V1.53102720", "V1.53102900"]
}
```

### Campos de filtrado

- **departments:** Lista de departamentos de la region Caribe
- **keywords:** Palabras clave para buscar en nombre y descripcion del proceso
- **unspsc_codes:** Codigos UNSPSC de categorias relevantes

### Logica de filtrado

Un proceso coincide si:
1. Su departamento esta en la lista del cliente, Y
2. Cumple AL MENOS UNO de:
   - Su codigo UNSPSC esta en la lista del cliente
   - Su nombre o descripcion contiene una keyword del cliente

---

## Monitoring

### Consultas SQL utiles

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

### Logs

Los logs se estructuran en JSON para facilitar el monitoreo:

```json
{
  "timestamp": "2026-08-29T15:00:00Z",
  "level": "info",
  "event": "job_completed",
  "processes_found": 127,
  "processes_matched": 3,
  "notifications_sent": 3
}
```

---

## Deploy a Produccion

### 1. Subir codigo a GitHub

```bash
cd /home/mery/projects/mvp_SECOP
git init
git add .
git commit -m "feat: MVP funcional - SECOP monitor con email"
git remote add origin https://github.com/TU_USUARIO/secop-monitor.git
git push -u origin main
```

### 2. Configurar GitHub Secrets

1. Ir al repositorio en GitHub
2. Settings > Secrets and variables > Actions
3. Click "New repository secret"
4. Agregar cada secret:

| Secret | Valor |
|--------|-------|
| `DATABASE_URL` | URL de Neon |
| `BREVO_API_KEY` | API key de Brevo |
| `SENDER_EMAIL` | `whoami_jay@proton.me` |
| `SENDER_NAME` | `SECOP Monitor` |
| `ADMIN_EMAIL` | `meriyei.manfer@gmail.com` |
| `STEALTH_MODE` | `false` (para envio real) |

**Nota:** Los secrets son write-only. No puedes verlos despues de crearlos, solo actualizarlos.

### 3. Verificar primera ejecucion

1. En GitHub, ir a pestaña "Actions" del repositorio
2. Seleccionar el workflow "SECOP Monitor"
3. Click "Run workflow" para ejecutar manualmente
4. Esperar a que complete (ver check verde ✓)
5. Click en la ejecucion para ver logs
6. Verificar tablas en Neon:
   - `job_runs` → status = "success"
   - `processes` → registros nuevos
   - `notifications` → emails enviados/fallidos

### 4. Activar envio de emails

Cuando confirmes que funciona:
1. En GitHub, ir a Settings > Secrets and variables > Actions
2. Actualizar `STEALTH_MODE` a `false`
3. Ejecutar workflow manualmente
4. Verificar que llegan correos

---

## Configuracion Dominio Propio en Brevo (Reducir Spam)

### Por que llegan a spam?

Brevo free tier usa dominio compartido `brevosend.com`. Gmail ve ese dominio como remitente y clasifica como spam. Con dominio propio, los emails llegan desde `tudominio.com` → confianza → inbox.

### Que es DNS?

DNS es el sistema que traduce nombres a direcciones. Cuando configuras dominio propio, agregas registros DNS que le dicen a Gmail: "este servidor esta autorizado para enviar emails en nombre de tudominio.com".

### Paso 1: Comprar dominio (~$10/año)

Opciones economicas:
- **Namecheap:** ~$8-12/año (.com, .co, .net)
- **Google Domains:** ~$12/año
- **Cloudflare Registrar:** ~$8/año (al costo, sin markup)
- **Porkbun:** ~$8-10/año

Recomendacion: `.com` o `.co` (Colombia). Evitar extensiones raras.

### Paso 2: Verificar dominio en Brevo

1. Ir a `https://app.brevo.com/settings/keys/sending`
2. Click "Add a domain"
3. Ingresar tu dominio (ej: `tumonitor.com`)
4. Brevo te da 3 registros DNS para agregar:

| Tipo | Nombre | Valor | Funcion |
|------|--------|-------|---------|
| TXT | `smtp._domainkey` | `k=rsa; p=MIGfMA0...` | DKIM - firma digital |
| TXT | `@` | `v=spf1 include:brevo.com ~all` | SPF - autoriza envio |
| CNAME | `brevo.code` | `send.brevo.com` | Tracking |

### Paso 3: Agregar registros en tu proveedor DNS

En Namecheap (ejemplo):
1. Dashboard > Domain List > Manage > Advanced DNS
2. Agregar registros uno por uno
3. Esperar propagacion (5 minutos - 48 horas, usualmente 1-2 horas)

En Cloudflare (ejemplo):
1. Dashboard > DNS > Records
2. Agregar registros (proxy OFF para email)

### Paso 4: Confirmar verificacion en Brevo

1. Volver a `https://app.brevo.com/settings/keys/sending`
2. Click "Verify" junto al dominio
3. Si propagation termino → verde ✓
4. Si no → esperar mas tiempo y reintentar

### Paso 5: Configurar sender con dominio propio

1. En Brevo > Senders > Add a sender
2. Email: `notificaciones@tudominio.com`
3. Nombre: `SECOP Monitor`
4. Verificar email (Brevo envia codigo)
5. Actualizar `.env`:
   ```
   SENDER_EMAIL=notificaciones@tudominio.com
   ```

### Resultado

| Antes | Despues |
|-------|---------|
| `SECOP Monitor <whoami_jay@12002987.brevosend.com>` | `SECOP Monitor <notificaciones@tudominio.com>` |
| 30-40% va a spam | <5% va a spam |
| Sin credibilidad | Dominio profesional |

### Costo total

| Item | Costo |
|------|-------|
| Dominio | ~$10/año |
| Brevo free tier | $0 |
| Total | ~$10/año |

---

## Fases de Validacion

### Fase 1: Stealth Mode (1 semana)

1. Configurar `STEALTH_MODE=true`
2. El sistema detecta y guarda procesos pero NO envia emails
3. Revisar resultados en la BD
4. Ajustar keywords/filtros segun feedback del cliente

### Fase 2: Produccion

1. Configurar `STEALTH_MODE=false`
2. Activar envio de emails
3. Monitorear ejecuciones en tabla `job_runs`

---

## Funcionalidades Futuras

Estas funcionalidades estan disenadas pero no implementadas en el MVP:

1. **WhatsApp** - Notificaciones por WhatsApp via Meta Cloud API
2. **Multi-tenant** - Multiples clientes con diferentes filtros
3. **Dashboard** - Panel web para gestionar filtros y ver historial
4. **Deteccion de cambios** - Notificar actualizaciones a procesos existentes
5. **Filtro por valor** - Excluir procesos por monto
6. **Filtro por entidad** - Incluir/excluir entidades especificas
7. **Filtro por modalidad** - Licitacion publica, seleccion abreviada, etc.
8. **Filtro por fecha limite** - Excluir procesos vencidos
9. **Web scraping de community.secop.gov.co** - Para menor latencia
10. **API OCDS** - Fuente alternativa mas rapida

---

## Estructura del Proyecto

```
secop-monitor/
├── Dockerfile
├── requirements.txt
├── .env.example
├── .env (no commitear - contiene secrets)
├── .gitignore
├── .github/
│   └── workflows/
│       └── secop.yml
├── README.md
├── config/
│   └── client_config.json
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── sources/
│   │   ├── base.py
│   │   └── secop.py
│   ├── filters/
│   │   └── engine.py
│   ├── database/
│   │   ├── connection.py
│   │   └── models.py
│   ├── notifications/
│   │   ├── base.py
│   │   └── email.py
│   └── models/
│       └── process.py
└── tests/
    ├── test_filters.py
    ├── test_secop_source.py
    ├── test_database.py
    └── test_notification.py
```

---

## Troubleshooting

### Error: `can't adapt type 'dict'`

**Causa:** Campo `urlproceso` de SECOP API devuelve dict `{'url': '...'}`, no string.

**Solucion:** Verificar que `secop.py` maneja correctamente:
```python
"url": raw.get("urlproceso", {}).get("url", "") if isinstance(raw.get("urlproceso"), dict) else str(raw.get("urlproceso", "")),
```

### Error: `ModuleNotFoundError: No module named 'structlog'`

**Causa:** Dependencias no instaladas.

**Solucion:**
```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### Error: `psycopg2.OperationalError: connection timeout`

**Causa:** Neon database en sleep mode (scale-to-zero).

**Solucion:** Neon tarda ~300-500ms en despertar. Normal en free tier. Si persiste, verificar `DATABASE_URL` y que Neon project esta activo.

### Emails van a spam

**Causa:** Brevo free tier usa dominio compartido `brevosend.com`.

**Solucion:** Configurar dominio propio (ver seccion "Configuracion Dominio Propio en Brevo").

### Error: `email_failed status=401`

**Causa:** API key de Brevo incorrecta o expirada.

**Solucion:** Verificar `BREVO_API_KEY` en `.env` y en `https://app.brevo.com/settings/keys/api`.

### Error: `email_failed status=400`

**Causa:** Email remitente no verificado en Brevo.

**Solucion:** Verificar `SENDER_EMAIL` en Brevo > Senders. Debe coincidir exactamente.

### Neon: `remaining_compute_hours` bajo

**Causa:** Free tier limit: 100 CU-hours/mes.

**Solucion:** Cada ejecucion usa ~0.1 CU-hour. 3 ejecuciones/dia = ~9 CU-hours/mes. Suficiente para MVP.

### GitHub Actions no se ejecuta

**Causa:** Cron jobs en GitHub Actions pueden tardar hasta 15 min en ejecutarse.

**Solucion:** Esperar o ejecutar manualmente via "Run workflow". Verificar que el workflow esta habilitado en la pestaña "Actions".

### GitHub Actions falla con error de permisos

**Causa:** Secrets no configurados o incorrectos.

**Solucion:** Verificar que todos los secrets esten configurados en Settings > Secrets and variables > Actions. Los secrets son write-only, no se pueden ver despues de crearlos.
