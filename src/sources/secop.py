import httpx
from typing import List, Dict, Optional
from .base import DataSource
import structlog

logger = structlog.get_logger()

BASE_URL = "https://www.datos.gov.co/resource/p6dx-8zbt.json"


class SecopDataSource(DataSource):
    def __init__(self, app_token: Optional[str] = None):
        self.app_token = app_token
        self.headers = {}
        if app_token:
            self.headers["X-App-Token"] = app_token

    def _build_where_clause(
        self,
        departments: List[str],
        status: str = "Publicado",
        phase: Optional[List[str]] = None,
        opening: str = "Abierto",
        adjudicated: str = "No",
    ) -> str:
        dept_list = ",".join(f"'{d}'" for d in departments)
        phase_list = ",".join(f"'{p}'" for p in (phase or ["Presentacion de oferta", "Fase de ofertas"]))

        parts = [
            f"departamento_entidad IN ({dept_list})",
            f"estado_del_procedimiento='{status}'",
            f"id_estado_del_procedimiento=50",
            f"fase IN ({phase_list})",
            f"estado_de_apertura_del_proceso='{opening}'",
            f"adjudicado='{adjudicated}'",
        ]
        return " AND ".join(parts)

    def _normalize_process(self, raw: Dict) -> Dict:
        return {
            "id": raw.get("id_del_proceso", ""),
            "entity_name": raw.get("entidad", ""),
            "entity_nit": raw.get("nit_entidad", ""),
            "department": raw.get("departamento_entidad", ""),
            "city": raw.get("ciudad_entidad", ""),
            "name": raw.get("nombre_del_procedimiento", ""),
            "description": raw.get("descripci_n_del_procedimiento", ""),
            "status": raw.get("estado_del_procedimiento", ""),
            "phase": raw.get("fase", ""),
            "contract_type": raw.get("tipo_de_contrato", ""),
            "modality": raw.get("modalidad_de_contratacion", ""),
            "base_price": float(raw.get("precio_base", 0) or 0),
            "publication_date": raw.get("fecha_de_publicacion_del", ""),
            "deadline": raw.get("fecha_de_recepcion_de", ""),
            "unspsc_code": raw.get("codigo_principal_de_categoria", ""),
            "url": raw.get("urlproceso", ""),
        }

    def fetch_processes(
        self,
        departments: List[str],
        limit: int = 5000,
    ) -> List[Dict]:
        where = self._build_where_clause(departments)
        all_processes = []
        offset = 0

        while True:
            params = {
                "$where": where,
                "$order": "fecha_de_publicacion_del DESC",
                "$limit": str(limit),
                "$offset": str(offset),
            }

            try:
                with httpx.Client(timeout=30) as client:
                    resp = client.get(BASE_URL, params=params, headers=self.headers)
                    resp.raise_for_status()
                    raw_data = resp.json()
            except Exception as e:
                logger.error("secop_api_error", error=str(e), offset=offset)
                break

            if not raw_data:
                break

            for item in raw_data:
                normalized = self._normalize_process(item)
                if normalized["id"]:
                    all_processes.append(normalized)

            logger.info("secop_page_fetched", count=len(raw_data), offset=offset)

            if len(raw_data) < limit:
                break
            offset += limit

        logger.info("secop_fetch_complete", total=len(all_processes))
        return all_processes
