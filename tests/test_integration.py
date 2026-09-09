import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from src.sources.secop import SecopDataSource
from src.filters.engine import FilterEngine, load_config


CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "client_config.json")


def test_api_returns_data():
    source = SecopDataSource()
    processes = source.fetch_processes(departments=["Atlántico"], limit=5, max_results=5)
    assert len(processes) > 0, "SECOP API returned no processes for Atlántico"
    assert processes[0].get("id") is not None


def test_filter_engine_works_with_real_data():
    source = SecopDataSource()
    config = load_config(CONFIG_PATH)
    engine = FilterEngine(config)

    processes = source.fetch_processes(
        departments=["Atlántico"], limit=20, max_results=20, modality="Mínima cuantía"
    )
    matched = engine.filter_batch(processes)

    for p in matched:
        modality_normalized = engine.normalize_text(p.get("modality", ""))
        assert "minima cuantia" in modality_normalized, \
            f"Process {p['id']} has unexpected modality: {p.get('modality')}"


def test_certifications_detection():
    emailer_config = load_config(CONFIG_PATH)
    engine = FilterEngine(emailer_config)

    process = {
        "id": "TEST.001",
        "name": "Dotación de uniformes para mujer líder",
        "description": "Empresa de mujeres con equidad de género",
        "department": "Atlántico",
        "modality": "Mínima cuantía",
    }
    certs = engine.detect_certifications(process)
    assert certs["favorece_mujer_lider"] is True
    assert certs["requiere_equidad_genero"] is True
    assert certs["favorece_pyme"] is False
