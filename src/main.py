import os
import sys
import json
import time
import structlog
from src.config import DATABASE_URL, SECOP_APP_TOKEN, STEALTH_MODE, ADMIN_EMAIL
from src.sources.secop import SecopDataSource
from src.filters.engine import FilterEngine, load_config
from src.database.connection import get_connection, init_db
from src.database.models import (
    compute_hash, save_process, mark_notified,
    start_job_run, complete_job_run, get_pending_notifications,
)
from src.notifications.email import EmailNotification

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
)
logger = structlog.get_logger()

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "client_config.json")


def main():
    logger.info("job_started", stealth=STEALTH_MODE)

    conn = get_connection(DATABASE_URL)
    init_db(conn)

    job_id = start_job_run(conn)

    try:
        config = load_config(CONFIG_PATH)
        departments = config.get("departments", [])

        source = SecopDataSource(app_token=SECOP_APP_TOKEN)
        processes = source.fetch_processes(departments=departments)
        logger.info("secop_fetched", count=len(processes))

        engine = FilterEngine(config)
        matched = engine.filter_batch(processes)

        new_ids = set()
        new_count = 0
        skip_count = 0
        for process in matched:
            h = compute_hash(process)
            is_new = save_process(conn, process, h)
            if is_new:
                new_count += 1
                new_ids.add(process["id"])
            else:
                skip_count += 1

        logger.info("filtering_done", new=new_count, skipped=skip_count)

        if not STEALTH_MODE and new_count > 0:
            emailer = EmailNotification()
            client_email = config.get("email", "")
            sent = 0
            failed = 0
            for process in matched:
                if process["id"] not in new_ids:
                    continue
                ok = emailer.send(process, client_email)
                if ok:
                    mark_notified(conn, process["id"], "email", "sent")
                    sent += 1
                else:
                    mark_notified(conn, process["id"], "email", "failed", "email send failed")
                    failed += 1
            logger.info("notifications_done", sent=sent, failed=failed)
            complete_job_run(conn, job_id, "success",
                           processes_found=len(processes),
                           processes_matched=len(matched),
                           notifications_sent=sent,
                           notifications_failed=failed)
        else:
            complete_job_run(conn, job_id, "success",
                           processes_found=len(processes),
                           processes_matched=len(matched),
                           notifications_sent=0,
                           notifications_failed=0)

    except Exception as e:
        logger.error("job_failed", error=str(e))
        complete_job_run(conn, job_id, "failed", error_message=str(e)[:500])
    finally:
        conn.close()

    logger.info("job_completed")


if __name__ == "__main__":
    main()
