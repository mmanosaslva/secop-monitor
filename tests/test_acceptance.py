import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from src.sources.secop import SecopDataSource
from src.filters.engine import FilterEngine, load_config


CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "client_config.json")


def _load():
    config = load_config(CONFIG_PATH)
    engine = FilterEngine(config)
    source = SecopDataSource()
    return config, engine, source


@pytest.mark.acceptance
def test_client_config_completeness():
    config, _, _ = _load()
    assert "departments" in config and len(config["departments"]) >= 5
    assert "unspsc_codes" in config and len(config["unspsc_codes"]) > 0
    assert "keywords" in config and len(config["keywords"]) > 0
    assert "modalidad_keywords" in config
    assert "certification_keywords" in config
    assert "email" in config


@pytest.mark.acceptance
def test_product_matching_dotacion():
    _, engine, _ = _load()
    process = {
        "id": "TEST.DOTACION.001",
        "name": "DOTACION DE UNIFORMES PARA OPERARIOS",
        "description": "SUMINISTRO DE DOTACION DE UNIFORMES",
        "department": "Atlántico",
        "modality": "Mínima cuantía",
    }
    assert engine.matches(process)


@pytest.mark.acceptance
def test_product_matching_epp():
    _, engine, _ = _load()
    process = {
        "id": "TEST.EPP.001",
        "name": "EPP ELEMENTOS DE PROTECCION PERSONAL",
        "description": "SUMINISTRO DE EPP PARA TRABAJADORES",
        "department": "Atlántico",
        "modality": "Mínima cuantía",
    }
    assert engine.matches(process)


@pytest.mark.acceptance
def test_modality_rejection_regimen_especial():
    _, engine, _ = _load()
    process = {
        "id": "TEST.RE.001",
        "name": "DOTACION UNIFORMES",
        "description": "DOTACION DE UNIFORMES",
        "department": "Atlántico",
        "modality": "Contratación régimen especial",
        "unspsc_code": "",
    }
    assert not engine.matches(process)


@pytest.mark.acceptance
def test_modality_rejection_contratacion_directa():
    _, engine, _ = _load()
    process = {
        "id": "TEST.CD.001",
        "name": "DOTACION DE UNIFORMES",
        "description": "DOTACION DE UNIFORMES",
        "department": "Atlántico",
        "modality": "Contratación directa",
        "unspsc_code": "",
    }
    assert not engine.matches(process)


@pytest.mark.acceptance
def test_mujer_lider_detection():
    _, engine, _ = _load()
    process = {
        "id": "TEST.ML.001",
        "name": "DOTACION DE UNIFORMES",
        "description": "EMPRESA DE MUJER LIDER",
        "department": "Atlántico",
        "modality": "Mínima cuantía",
    }
    certs = engine.detect_certifications(process)
    assert certs["favorece_mujer_lider"] is True


@pytest.mark.acceptance
def test_equidad_genero_detection():
    _, engine, _ = _load()
    process = {
        "id": "TEST.EG.001",
        "name": "DOTACION DE UNIFORMES",
        "description": "CON EQUIDAD DE GENERO",
        "department": "Atlántico",
        "modality": "Mínima cuantía",
    }
    certs = engine.detect_certifications(process)
    assert certs["requiere_equidad_genero"] is True


@pytest.mark.acceptance
def test_pyme_detection():
    _, engine, _ = _load()
    process = {
        "id": "TEST.PYME.001",
        "name": "DOTACION DE UNIFORMES",
        "description": "MICROEMPRESA PYME",
        "department": "Atlántico",
        "modality": "Mínima cuantía",
    }
    certs = engine.detect_certifications(process)
    assert certs["favorece_pyme"] is True
