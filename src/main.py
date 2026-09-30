import os
import sys
import json
import time
from collections import Counter

import structlog
from psycopg2.extras import Json
from src.config import DATABASE_URL, SECOP_APP_TOKEN, STEALTH_MODE, ADMIN_EMAIL
from src.sources.secop import SecopDataSource
from src.filters.engine import FilterEngine, load_config
from src.database.connection import get_connection, init_db
from src.database.models import (
    compute_hash, save_process, mark_notified,
    start_job_run, complete_job_run, get_pending_notifications,
    record_run_match, get_deliveries_to_refresh, update_delivery_status,
)
from src.ejecucion import contexto_de_ejecucion
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

    config = load_config(CONFIG_PATH)
    client_email = config.get("email", "")
    job_id = start_job_run(conn, contexto_de_ejecucion(client_email, STEALTH_MODE))

    try:
        departments = config.get("departments", [])

        source = SecopDataSource(app_token=SECOP_APP_TOKEN)
        processes = source.fetch_processes(departments=departments, modality="Mínima cuantía")
        logger.info("secop_fetched", count=len(processes))

        # Se evalua cada proceso una vez: la coincidencia y su motivo quedan
        # registrados para que la web explique que paso en este ciclo.
        engine = FilterEngine(config)
        matched = []
        descartes = Counter()
        for process in processes:
            coincide, motivo = engine.evaluate(process)
            if coincide:
                process["match_reason"] = motivo
                matched.append(process)
            else:
                descartes[motivo] += 1
        logger.info("filter_complete", total=len(processes), matched=len(matched))

        new_ids = set()
        new_count = 0
        skip_count = 0
        for process in matched:
            h = compute_hash(process)
            certs = engine.detect_certifications(process)
            process["certifications"] = certs
            is_new = save_process(conn, process, h, certs)
            record_run_match(conn, job_id, process["id"], is_new, process["match_reason"])
            if is_new:
                new_count += 1
                new_ids.add(process["id"])
            else:
                skip_count += 1

        logger.info("filtering_done", new=new_count, skipped=skip_count)

        sent = 0
        failed = 0
        emailer = EmailNotification()
        if not STEALTH_MODE and new_count > 0:
            for process in matched:
                if process["id"] not in new_ids:
                    continue
                certs = process.get("certifications", {})
                ok, error_msg = emailer.send(process, client_email, certs)
                if ok:
                    mark_notified(conn, process["id"], "email", "sent",
                                  job_run_id=job_id, message_id=emailer.last_message_id)
                    sent += 1
                else:
                    mark_notified(conn, process["id"], "email", "failed", error_msg,
                                  job_run_id=job_id)
                    failed += 1
                time.sleep(3)
            logger.info("notifications_done", sent=sent, failed=failed)

        complete_job_run(conn, job_id, "success",
                         processes_found=len(processes),
                         processes_matched=len(matched),
                         processes_new=new_count,
                         notifications_sent=sent,
                         notifications_failed=failed,
                         discard_summary=Json(dict(descartes)))

        # Pregunta a Brevo por los correos de los ultimos dias, incluidos los
        # de este ciclo. Un fallo aqui no invalida la ejecucion.
        actualizar_entregas(conn, emailer)

    except Exception as e:
        logger.error("job_failed", error=str(e))
        complete_job_run(conn, job_id, "failed", error_message=str(e)[:500])
    finally:
        conn.close()

    logger.info("job_completed")


def actualizar_entregas(conn, emailer):
    try:
        pendientes = get_deliveries_to_refresh(conn)
    except Exception as e:
        logger.warning("deliveries_query_failed", error=str(e))
        return
    for fila in pendientes:
        estado = emailer.delivery_status(fila["message_id"])
        if estado and estado != fila.get("delivery_status"):
            update_delivery_status(conn, fila["id"], estado)
    logger.info("deliveries_refreshed", checked=len(pendientes))


if __name__ == "__main__":
    main()
