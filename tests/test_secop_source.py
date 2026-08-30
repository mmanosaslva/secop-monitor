import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.sources.secop import SecopDataSource


def test_build_where_clause():
    source = SecopDataSource()
    where = source._build_where_clause(["Atlantico", "Bolivar"])
    assert "departamento_entidad IN ('Atlantico','Bolivar')" in where
    assert "estado_del_procedimiento='Publicado'" in where
    assert "id_estado_del_procedimiento=50" in where
    assert "adjudicado='No'" in where


def test_normalize_process():
    source = SecopDataSource()
    raw = {
        "id_del_proceso": "CO1.REQ.1234567",
        "entidad": "Alcaldia de Barranquilla",
        "nit_entidad": "890000000",
        "departamento_entidad": "Atlantico",
        "ciudad_entidad": "Barranquilla",
        "nombre_del_procedimiento": "Suministro de uniformes",
        "descripci_n_del_procedimiento": "500 uniformes deportivos",
        "estado_del_procedimiento": "Publicado",
        "fase": "Presentacion de oferta",
        "tipo_de_contrato": "Suministros",
        "modalidad_de_contratacion": "Licitacion publica",
        "precio_base": "50000000",
        "fecha_de_publicacion_del": "2026-08-29T00:00:00",
        "codigo_principal_de_categoria": "V1.53102700",
        "urlproceso": "https://community.secop.gov.co/...",
    }
    normalized = source._normalize_process(raw)
    assert normalized["id"] == "CO1.REQ.1234567"
    assert normalized["entity_name"] == "Alcaldia de Barranquilla"
    assert normalized["base_price"] == 50000000.0
    assert normalized["unspsc_code"] == "V1.53102700"
