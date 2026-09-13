# SECOP Monitor

Monitoreo automatico de contratacion publica en SECOP II (Colombia). Detecta procesos relevantes por departamento, modalidad y keywords, y envia notificaciones por email con badges de certificacion.

## Stack (100% gratis)

- **Runtime:** Python 3.11+
- **DB:** Neon PostgreSQL (free tier)
- **Email:** Brevo API (free tier)
- **Cron:** GitHub Actions (4x/dia)
- **Fuente:** SECOP II / datos.gov.co

## Instalacion

```bash
git clone https://github.com/mmanoslasva/secop-monitor.git
cd secop-monitor
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Variables de entorno

Copiar `.env.example` a `.env` y configurar:

```bash
DATABASE_URL=postgresql://user:pass@ep-xxx.neon.tech/neondb?sslmode=require
BREVO_API_KEY=xkeysib-...
SENDER_EMAIL=oportunidades.secop@outlook.com
SENDER_NAME=SECOP Monitor
ADMIN_EMAIL=tu@email.com
STEALTH_MODE=false
```

## Uso

### Ejecutar local

```bash
python -m src.main
```

### Ejecutar en produccion

El cron ejecuta 4 veces al dia (00:45, 10:00, 13:30, 20:00 COT).

Ejecutar manual: GitHub > Actions > SECOP Monitor > Run workflow.

## Configuracion

Archivo `config/client_config.json`:

```json
{
  "name": "Cliente Textil Caribe",
  "email": "cliente@email.com",
  "departments": ["Atlantico", "Bolivar", "Magdalena", "Cordoba", "Sucre", "La Guajira", "Cesar"],
  "keywords": ["uniforme", "ropa deportiva", "vestuario", "calzado", "dotacion", "textil"],
  "unspsc_codes": ["V1.53102700", "V1.53102710"],
  "certification_keywords": ["mujer lider", "equidad de genero", "pyme"],
  "modalidad_keywords": ["minima cuantia"]
}
```

### Logica de filtrado

Un proceso se notifica si:
1. Departamento esta en la lista
2. Modalidad es "minima cuantia"
3. Keywords o UNSPSC code matchean

Las certificaciones (mujer lider, equidad genero, PYME) son badges informativos, no requisito.

## Estructura

```
secop-monitor/
├── .github/workflows/secop.yml    # Cron
├── config/client_config.json      # Filtros del cliente
├── src/
│   ├── main.py                    # Entry point
│   ├── config.py                  # Env vars
│   ├── sources/secop.py           # SECOP API
│   ├── filters/engine.py          # Motor de filtros
│   ├── database/connection.py     # Neon DB
│   ├── database/models.py         # CRUD
│   └── notifications/email.py     # Brevo email
├── tests/
├── requirements.txt
└── .env
```

## Tests

```bash
pytest tests/ -v
```

53 tests: filtros, notificaciones, DB, SECOP, integracion, aceptacion.
