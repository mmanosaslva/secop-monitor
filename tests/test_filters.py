import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.filters.engine import FilterEngine


def make_process(**kwargs):
    defaults = {
        "id": "CO1.REQ.1234567",
        "entity_name": "Alcaldia de Barranquilla",
        "department": "Atlantico",
        "city": "Barranquilla",
        "name": "Suministro de uniformes deportivos",
        "description": "Suministro de 500 uniformes para escuelas deportivas",
        "status": "Publicado",
        "phase": "Presentacion de oferta",
        "unspsc_code": "V1.53102700",
        "base_price": 50000000,
    }
    defaults.update(kwargs)
    return defaults


def test_match_by_keyword():
    config = {
        "departments": ["Atlantico"],
        "keywords": ["uniforme", "ropa deportiva"],
        "unspsc_codes": [],
    }
    engine = FilterEngine(config)
    p = make_process()
    assert engine.matches(p) is True


def test_no_match_wrong_department():
    config = {
        "departments": ["Bolivar"],
        "keywords": ["uniforme"],
        "unspsc_codes": [],
    }
    engine = FilterEngine(config)
    p = make_process(department="Atlantico")
    assert engine.matches(p) is False


def test_match_by_unspsc():
    config = {
        "departments": ["Atlantico"],
        "keywords": [],
        "unspsc_codes": ["V1.53102700"],
    }
    engine = FilterEngine(config)
    p = make_process()
    assert engine.matches(p) is True


def test_no_match_keyword_case_insensitive():
    config = {
        "departments": ["Atlantico"],
        "keywords": ["UNIFORME"],
        "unspsc_codes": [],
    }
    engine = FilterEngine(config)
    p = make_process(name="suministro de Uniformes deportivos")
    assert engine.matches(p) is True


def test_filter_batch():
    config = {
        "departments": ["Atlantico", "Bolivar"],
        "keywords": ["uniforme"],
        "unspsc_codes": [],
    }
    engine = FilterEngine(config)
    processes = [
        make_process(id="CO1.REQ.001", department="Atlantico", name="Uniformes"),
        make_process(id="CO1.REQ.002", department="Bolivar", name="Medicamentos", description="Compra de medicamentos"),
        make_process(id="CO1.REQ.003", department="Atlantico", name="Computadores", description="Compra de computadores"),
    ]
    matched = engine.filter_batch(processes)
    assert len(matched) == 1
    assert matched[0]["id"] == "CO1.REQ.001"
