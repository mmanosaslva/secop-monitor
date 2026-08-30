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


def save_process(conn, process: Dict, content_hash: str) -> bool:
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO processes (id, entity_name, entity_nit, department, city,
                name, description, status, phase, contract_type, modality,
                base_price, publication_date, deadline, unspsc_code, url, content_hash)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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


def mark_notified(conn, process_id: str, channel: str, status: str, error_message: str = None):
    cursor = conn.cursor()
    try:
        if status == "sent":
            cursor.execute(
                "UPDATE processes SET notified = TRUE WHERE id = %s",
                (process_id,),
            )
        cursor.execute(
            """
            INSERT INTO notifications (process_id, channel, status, sent_at, error_message)
            VALUES (%s, %s, %s, NOW(), %s)
            """,
            (process_id, channel, status, error_message),
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


def start_job_run(conn) -> int:
    cursor = conn.cursor()
    cursor.execute("INSERT INTO job_runs (status) VALUES ('running') RETURNING id")
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
