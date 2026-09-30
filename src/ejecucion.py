"""Contexto de la ejecucion actual del motor.

En GitHub Actions el runner expone variables GITHUB_*; con ellas cada fila de
job_runs queda enlazada a su run y a su ciclo. Fuera de Actions (local o
pruebas) los campos de GitHub quedan vacios y el trigger es 'local'.
"""
import json
import os
from datetime import datetime, timezone
from typing import Dict

from src.ciclos import ciclo_mas_cercano, ciclo_por_cron


def _cron_del_evento() -> str:
    """Expresion cron que disparo el run, leida del payload del evento."""
    ruta = os.environ.get("GITHUB_EVENT_PATH")
    if not ruta or not os.path.exists(ruta):
        return ""
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f).get("schedule", "") or ""
    except (OSError, ValueError):
        return ""


def contexto_de_ejecucion(recipient: str, stealth: bool, ahora: datetime = None) -> Dict:
    ahora = ahora or datetime.now(timezone.utc)
    run_id = os.environ.get("GITHUB_RUN_ID")
    repo = os.environ.get("GITHUB_REPOSITORY")
    servidor = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    evento = os.environ.get("GITHUB_EVENT_NAME")

    ciclo = ciclo_por_cron(_cron_del_evento()) if evento == "schedule" else None
    return {
        "github_run_id": int(run_id) if run_id and run_id.isdigit() else None,
        "github_run_url": f"{servidor}/{repo}/actions/runs/{run_id}" if run_id and repo else None,
        "trigger": evento or "local",
        "ciclo": ciclo or ciclo_mas_cercano(ahora),
        "recipient": recipient,
        "stealth": stealth,
    }
