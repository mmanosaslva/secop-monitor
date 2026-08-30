import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.database.models import compute_hash


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
