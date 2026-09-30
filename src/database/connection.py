import psycopg2
from psycopg2.extras import RealDictCursor
import structlog

logger = structlog.get_logger()


def get_connection(database_url: str):
    conn = psycopg2.connect(database_url)
    conn.autocommit = True
    return conn


def init_db(conn):
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS processes (
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
            content_hash TEXT,
            modalidad_seleccion TEXT,
            cuantia NUMERIC,
            favorece_mujer_lider BOOLEAN DEFAULT FALSE,
            favorece_pyme BOOLEAN DEFAULT FALSE,
            requiere_equidad_genero BOOLEAN DEFAULT FALSE
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id SERIAL PRIMARY KEY,
            process_id TEXT NOT NULL REFERENCES processes(id),
            channel TEXT NOT NULL CHECK (channel IN ('email', 'whatsapp')),
            status TEXT NOT NULL CHECK (status IN ('pending', 'sent', 'failed')),
            sent_at TIMESTAMPTZ,
            error_message TEXT,
            retry_count INT DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS job_runs (
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
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS client_config (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone_whatsapp TEXT,
            departments JSONB NOT NULL DEFAULT '[]',
            keywords JSONB NOT NULL DEFAULT '[]',
            unspsc_codes JSONB NOT NULL DEFAULT '[]',
            certification_keywords JSONB DEFAULT '[]',
            modalidad_keywords JSONB DEFAULT '[]',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    migrar_trazabilidad(cursor)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_processes_status ON processes(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_processes_department ON processes(department);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_processes_detected ON processes(detected_at);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_processes_notified ON processes(notified);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_process ON notifications(process_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_status ON notifications(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_job_runs_started ON job_runs(started_at);")
    cursor.close()
    logger.info("database_initialized")


def migrar_trazabilidad(cursor):
    """Columnas y tablas para seguir cada ejecucion del cron desde la web.

    Solo agrega (IF NOT EXISTS): se puede correr sobre una base con datos sin
    perder nada, y el motor la ejecuta al arrancar cada ciclo.
    """
    # Que ejecucion de GitHub Actions fue, que ciclo cubria y que resumio.
    for columna in (
        "github_run_id BIGINT",
        "github_run_url TEXT",
        "trigger TEXT",
        "ciclo TEXT",
        "recipient TEXT",
        "stealth BOOLEAN",
        "processes_new INT DEFAULT 0",
        "discard_summary JSONB DEFAULT '{}'::jsonb",
    ):
        cursor.execute(f"ALTER TABLE job_runs ADD COLUMN IF NOT EXISTS {columna};")

    # Cada correo sabe que ejecucion lo envio y que dijo Brevo despues.
    for columna in (
        "job_run_id INT",
        "message_id TEXT",
        "delivery_status TEXT",
        "delivery_updated_at TIMESTAMPTZ",
    ):
        cursor.execute(f"ALTER TABLE notifications ADD COLUMN IF NOT EXISTS {columna};")

    # Procesos que coincidieron en cada ejecucion. Los descartados no se
    # guardan uno a uno (serian miles por dia): se resumen en discard_summary.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS run_matches (
            job_run_id INT NOT NULL REFERENCES job_runs(id),
            process_id TEXT NOT NULL REFERENCES processes(id),
            is_new BOOLEAN NOT NULL DEFAULT FALSE,
            match_reason TEXT,
            PRIMARY KEY (job_run_id, process_id)
        );
    """)

    # Lo unico que escribe la web: que evento ya vio cada usuario.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notification_reads (
            user_id TEXT NOT NULL,
            event_key TEXT NOT NULL,
            read_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (user_id, event_key)
        );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_run ON notifications(job_run_id);")
