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
            content_hash TEXT
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
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_processes_status ON processes(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_processes_department ON processes(department);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_processes_detected ON processes(detected_at);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_processes_notified ON processes(notified);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_process ON notifications(process_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_status ON notifications(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_job_runs_started ON job_runs(started_at);")
    cursor.close()
    logger.info("database_initialized")
