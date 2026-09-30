import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, MagicMock
from src.main import main
from src.database.connection import get_connection, init_db
from src.database.models import start_job_run, complete_job_run

# Estas pruebas corren el motor completo y escriben en la base que reciben.
# Antes usaban DATABASE_URL, es decir, la base de PRODUCCION: cada ejecucion
# dejaba filas falsas en job_runs que la web mostraba como ciclos del cron.
# Ahora exigen una base aparte y se saltan si no la hay.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
requiere_base_de_pruebas = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="Define TEST_DATABASE_URL con una base de pruebas (nunca la de produccion)")


@requiere_base_de_pruebas
@pytest.mark.integration
@pytest.mark.slow
def test_main_runs_in_stealth_mode():
    db_url = TEST_DATABASE_URL
    with patch("src.main.DATABASE_URL", db_url), \
         patch("src.main.STEALTH_MODE", True), \
         patch("src.main.SECOP_APP_TOKEN", None), \
         patch("src.main.ADMIN_EMAIL", "test@test.com"):
        main()


@requiere_base_de_pruebas
@pytest.mark.integration
@pytest.mark.slow
def test_main_creates_job_run():
    db_url = TEST_DATABASE_URL
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
