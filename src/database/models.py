import hashlib
import json
from typing import Optional, Dict, List
import structlog

logger = structlog.get_logger()


def compute_hash(process: Dict) -> str:
    fields = {
        "name": process.get("name", ""),
        "description": process.get("description", ""),
        "status": process.get("status", ""),
        "phase": process.get("phase", ""),
        "base_price": process.get("base_price", 0),
        "deadline": process.get("deadline", ""),
        "url": process.get("url", ""),
    }
    return hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()


def save_process(conn, process: Dict, content_hash: str, certifications: Dict = None) -> bool:
    certifications = certifications or {}
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO processes (id, entity_name, entity_nit, department, city,
                name, description, status, phase, contract_type, modality,
                base_price, publication_date, deadline, unspsc_code, url, content_hash,
                modalidad_seleccion, cuantia, favorece_mujer_lider, favorece_pyme, requiere_equidad_genero)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                process["id"], process.get("entity_name"), process.get("entity_nit"),
                process.get("department"), process.get("city"), process.get("name"),
                process.get("description"), process.get("status"), process.get("phase"),
                process.get("contract_type"), process.get("modality"),
                process.get("base_price"), process.get("publication_date") or None,
                process.get("deadline") or None, process.get("unspsc_code"),
                process.get("url"), content_hash,
                process.get("modality"), process.get("base_price"),
                certifications.get("favorece_mujer_lider", False),
                certifications.get("favorece_pyme", False),
                certifications.get("requiere_equidad_genero", False),
            ),
        )
        inserted = cursor.rowcount > 0
        conn.commit()
        return inserted
    except Exception as e:
        conn.rollback()
        logger.error("save_process_error", process_id=process["id"], error=str(e))
        return False
    finally:
        cursor.close()


def mark_notified(conn, process_id: str, channel: str, status: str, error_message: str = None,
                  job_run_id: int = None, message_id: str = None):
    cursor = conn.cursor()
    try:
        if status == "sent":
            cursor.execute(
                "UPDATE processes SET notified = TRUE WHERE id = %s",
                (process_id,),
            )
        cursor.execute(
            """
            INSERT INTO notifications (process_id, channel, status, sent_at, error_message,
                job_run_id, message_id, delivery_status, delivery_updated_at)
            VALUES (%s, %s, %s, NOW(), %s, %s, %s, %s, NOW())
            """,
            (process_id, channel, status, error_message, job_run_id, message_id,
             "enviado" if status == "sent" else "fallido"),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error("mark_notified_error", process_id=process_id, error=str(e))
    finally:
        cursor.close()


def get_pending_notifications(conn) -> List[Dict]:
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT n.id, n.process_id, p.name, p.entity_name, p.department, p.city,
               p.base_price, p.publication_date, p.deadline, p.contract_type,
               p.modality, p.url, p.description
        FROM notifications n
        JOIN processes p ON n.process_id = p.id
        WHERE n.status = 'failed' AND n.retry_count < 3
        """
    )
    cols = [desc[0] for desc in cursor.description]
    results = [dict(zip(cols, row)) for row in cursor.fetchall()]
    cursor.close()
    return results


def start_job_run(conn, meta: Dict = None) -> int:
    """Abre la ejecucion. `meta` trae el contexto de GitHub Actions (ver
    src/ejecucion.py); sin el, la fila queda como antes."""
    meta = meta or {}
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO job_runs (status, github_run_id, github_run_url, trigger, ciclo,
            recipient, stealth)
        VALUES ('running', %s, %s, %s, %s, %s, %s) RETURNING id
        """,
        (meta.get("github_run_id"), meta.get("github_run_url"), meta.get("trigger"),
         meta.get("ciclo"), meta.get("recipient"), meta.get("stealth")),
    )
    job_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()
    return job_id


def complete_job_run(conn, job_id: int, status: str, **kwargs):
    cursor = conn.cursor()
    sets = ["completed_at = NOW()", "status = %s"]
    vals = [status]
    for key, val in kwargs.items():
        sets.append(f"{key} = %s")
        vals.append(val)
    vals.append(job_id)
    cursor.execute(f"UPDATE job_runs SET {', '.join(sets)} WHERE id = %s", vals)
    conn.commit()
    cursor.close()


def get_latest_job_run(conn) -> Optional[Dict]:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM job_runs ORDER BY started_at DESC LIMIT 1")
    cols = [desc[0] for desc in cursor.description]
    row = cursor.fetchone()
    cursor.close()
    if row:
        return dict(zip(cols, row))
    return None


def get_stats(conn) -> Dict:
    cursor = conn.cursor()
    stats = {}

    cursor.execute("SELECT COUNT(*) FROM processes WHERE detected_at >= CURRENT_DATE")
    stats["detected_today"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM processes WHERE notified = TRUE AND detected_at >= CURRENT_DATE")
    stats["notified_today"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM notifications WHERE status = 'failed' AND retry_count < 3")
    stats["pending_retries"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM processes")
    stats["total_processes"] = cursor.fetchone()[0]

    cursor.close()
    return stats


def record_run_match(conn, job_run_id: int, process_id: str, is_new: bool, match_reason: str):
    """Anota que un proceso coincidio en esta ejecucion (nuevo o ya conocido)."""
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO run_matches (job_run_id, process_id, is_new, match_reason)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (job_run_id, process_id) DO NOTHING
            """,
            (job_run_id, process_id, is_new, match_reason),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error("record_run_match_error", process_id=process_id, error=str(e))
    finally:
        cursor.close()


def get_deliveries_to_refresh(conn, days: int = 7) -> List[Dict]:
    """Correos enviados cuyo estado de entrega aun puede cambiar."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, message_id, delivery_status FROM notifications
        WHERE status = 'sent' AND message_id IS NOT NULL
          AND sent_at >= NOW() - (%s || ' days')::interval
          AND COALESCE(delivery_status, 'enviado') IN ('enviado', 'diferido', 'entregado')
        """,
        (str(days),),
    )
    cols = [desc[0] for desc in cursor.description]
    results = [dict(zip(cols, row)) for row in cursor.fetchall()]
    cursor.close()
    return results


def update_delivery_status(conn, notification_id: int, delivery_status: str):
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE notifications SET delivery_status = %s, delivery_updated_at = NOW()
            WHERE id = %s AND delivery_status IS DISTINCT FROM %s
            """,
            (delivery_status, notification_id, delivery_status),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error("update_delivery_error", notification_id=notification_id, error=str(e))
    finally:
        cursor.close()
