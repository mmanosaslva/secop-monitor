import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, MagicMock
from src.main import main
from src.database.connection import get_connection, init_db
from src.database.models import start_job_run, complete_job_run


@pytest.mark.integration
@pytest.mark.slow
def test_main_runs_in_stealth_mode():
    db_url = os.environ.get("DATABASE_URL", "sqlite:///test_main.db")
    with patch("src.main.DATABASE_URL", db_url), \
         patch("src.main.STEALTH_MODE", True), \
         patch("src.main.SECOP_APP_TOKEN", None), \
         patch("src.main.ADMIN_EMAIL", "test@test.com"):
        main()


@pytest.mark.integration
@pytest.mark.slow
def test_main_creates_job_run():
    db_url = os.environ.get("DATABASE_URL", "sqlite:///test_main.db")
    with patch("src.main.DATABASE_URL", db_url), \
         patch("src.main.STEALTH_MODE", True), \
         patch("src.main.SECOP_APP_TOKEN", None), \
         patch("src.main.ADMIN_EMAIL", "test@test.com"):
        main()

    conn = get_connection(db_url)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM job_runs")
    count = cursor.fetchone()[0]
    conn.close()
    assert count >= 1, "Job run not recorded in database"
