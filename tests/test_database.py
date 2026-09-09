import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock, patch
from src.database.models import compute_hash, save_process


def test_compute_hash_deterministic():
    process = {
        "name": "Suministro de uniformes",
        "description": "500 uniformes deportivos",
        "status": "Publicado",
        "phase": "Presentacion de oferta",
        "base_price": 50000000,
        "deadline": "2026-09-15",
        "url": "https://community.secop.gov.co/...",
    }
    h1 = compute_hash(process)
    h2 = compute_hash(process)
    assert h1 == h2


def test_compute_hash_changes_with_data():
    process1 = {
        "name": "Uniformes",
        "description": "desc",
        "status": "Publicado",
        "phase": "Presentacion de oferta",
        "base_price": 100,
        "deadline": "",
        "url": "",
    }
    process2 = {
        "name": "Uniformes",
        "description": "desc",
        "status": "Publicado",
        "phase": "Presentacion de oferta",
        "base_price": 200,
        "deadline": "",
        "url": "",
    }
    assert compute_hash(process1) != compute_hash(process2)


def test_save_process_new():
    mock_cursor = MagicMock()
    mock_cursor.rowcount = 1
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    process = {
        "id": "CO1.REQ.1234567",
        "entity_name": "Test",
        "entity_nit": "123",
        "department": "Atlantico",
        "city": "Barranquilla",
        "name": "Test",
        "description": "Test",
        "status": "Publicado",
        "phase": "Presentacion",
        "contract_type": "Suministros",
        "modality": "Mínima cuantía",
        "base_price": 50000,
        "publication_date": "2026-01-01",
        "deadline": "2026-12-31",
        "unspsc_code": "V1.53102700",
        "url": "http://test.com",
    }
    certs = {"favorece_mujer_lider": False, "favorece_pyme": True, "requiere_equidad_genero": False}

    result = save_process(mock_conn, process, "hash123", certs)
    assert result is True
    mock_cursor.execute.assert_called_once()
    mock_conn.commit.assert_called_once()


def test_save_process_existing():
    mock_cursor = MagicMock()
    mock_cursor.rowcount = 0
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    process = {
        "id": "CO1.REQ.1234567",
        "entity_name": "Test",
        "entity_nit": "123",
        "department": "Atlantico",
        "city": "Barranquilla",
        "name": "Test",
        "description": "Test",
        "status": "Publicado",
        "phase": "Presentacion",
        "contract_type": "Suministros",
        "modality": "Mínima cuantía",
        "base_price": 50000,
        "publication_date": "2026-01-01",
        "deadline": "2026-12-31",
        "unspsc_code": "V1.53102700",
        "url": "http://test.com",
    }

    result = save_process(mock_conn, process, "hash123")
    assert result is False
