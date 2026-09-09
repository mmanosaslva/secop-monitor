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
        "modality": "Mínima cuantía",
        "unspsc_code": "V1.53102700",
        "base_price": 50000000,
    }
    defaults.update(kwargs)
    return defaults


def make_config(**kwargs):
    defaults = {
        "departments": ["Atlantico"],
        "keywords": ["uniforme", "ropa deportiva"],
        "unspsc_codes": ["V1.53102700"],
        "certification_keywords": [],
        "modalidad_keywords": ["mínima cuantía"],
    }
    defaults.update(kwargs)
    return defaults


def test_match_by_keyword():
    config = make_config(keywords=["uniforme", "ropa deportiva"], unspsc_codes=[])
    engine = FilterEngine(config)
    p = make_process()
    assert engine.matches(p) is True


def test_no_match_wrong_department():
    config = make_config(departments=["Bolivar"])
    engine = FilterEngine(config)
    p = make_process(department="Atlantico")
    assert engine.matches(p) is False


def test_match_by_unspsc():
    config = make_config(unspsc_codes=["V1.53102700"], keywords=[])
    engine = FilterEngine(config)
    p = make_process()
    assert engine.matches(p) is True


def test_no_match_keyword_case_insensitive():
    config = make_config(keywords=["UNIFORME"], unspsc_codes=[])
    engine = FilterEngine(config)
    p = make_process(name="suministro de Uniformes deportivos")
    assert engine.matches(p) is True


def test_filter_batch():
    config = make_config(departments=["Atlantico", "Bolivar"], keywords=["uniforme"], unspsc_codes=[])
    engine = FilterEngine(config)
    processes = [
        make_process(id="CO1.REQ.001", department="Atlantico", name="Uniformes"),
        make_process(id="CO1.REQ.002", department="Bolivar", name="Medicamentos", description="Compra de medicamentos"),
        make_process(id="CO1.REQ.003", department="Atlantico", name="Computadores", description="Compra de computadores"),
    ]
    matched = engine.filter_batch(processes)
    assert len(matched) == 1
    assert matched[0]["id"] == "CO1.REQ.001"


def test_normalize_text_quita_tildes():
    config = make_config()
    engine = FilterEngine(config)
    assert engine.normalize_text("Mínima Cuantía") == "minima cuantia"


def test_normalize_text_lowercase():
    config = make_config()
    engine = FilterEngine(config)
    assert engine.normalize_text("MINIMA CUANTIA") == "minima cuantia"


def test_match_by_modalidad():
    config = make_config(keywords=["uniforme"], unspsc_codes=[])
    engine = FilterEngine(config)
    p = make_process(modality="Mínima cuantía")
    assert engine.matches(p) is True


def test_no_match_wrong_modalidad():
    config = make_config(keywords=["uniforme"], unspsc_codes=[])
    engine = FilterEngine(config)
    p = make_process(modality="Contratación directa")
    assert engine.matches(p) is False


def test_modalidad_case_insensitive():
    config = make_config(keywords=["uniforme"], unspsc_codes=[])
    engine = FilterEngine(config)
    p = make_process(modality="MINIMA CUANTIA")
    assert engine.matches(p) is True


def test_modalidad_with_accents():
    config = make_config(keywords=["uniforme"], unspsc_codes=[])
    engine = FilterEngine(config)
    p = make_process(modality="Mínima Cuantía")
    assert engine.matches(p) is True


def test_match_by_certification_keyword():
    config = make_config(keywords=[], unspsc_codes=[], certification_keywords=["mujer lider"])
    engine = FilterEngine(config)
    p = make_process(name="Dotacion uniformes mujer lider")
    assert engine.matches(p) is True


def test_detect_certifications_mujer_lider():
    config = make_config()
    engine = FilterEngine(config)
    p = make_process(name="Proceso mujer líder")
    certs = engine.detect_certifications(p)
    assert certs["favorece_mujer_lider"] is True


def test_detect_certifications_equidad_genero():
    config = make_config()
    engine = FilterEngine(config)
    p = make_process(description="Equidad de género")
    certs = engine.detect_certifications(p)
    assert certs["requiere_equidad_genero"] is True


def test_detect_certifications_pyme():
    config = make_config()
    engine = FilterEngine(config)
    p = make_process(name="Empresa PYME")
    certs = engine.detect_certifications(p)
    assert certs["favorece_pyme"] is True


def test_detect_certifications_none():
    config = make_config()
    engine = FilterEngine(config)
    p = make_process(name="Dotacion uniformes", description="Suministro normal")
    certs = engine.detect_certifications(p)
    assert certs["favorece_mujer_lider"] is False
    assert certs["favorece_pyme"] is False
    assert certs["requiere_equidad_genero"] is False


def test_no_match_empty_modalidad_keywords():
    config = make_config(modalidad_keywords=[], keywords=[], unspsc_codes=[])
    engine = FilterEngine(config)
    p = make_process()
    assert engine.matches(p) is False
