import unicodedata
import json
from typing import List, Dict
import structlog

logger = structlog.get_logger()


class FilterEngine:
    def __init__(self, config: Dict):
        self.departments = config.get("departments", [])
        self.keywords = [kw.upper() for kw in config.get("keywords", [])]
        self.unspsc_codes = config.get("unspsc_codes", [])
        self.certification_keywords = [kw.upper() for kw in config.get("certification_keywords", [])]
        self.modalidad_keywords = [self.normalize_text(kw) for kw in config.get("modalidad_keywords", [])]

    def normalize_text(self, text: str) -> str:
        text = unicodedata.normalize('NFD', text)
        text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
        return text.lower().strip()

    def matches(self, process: Dict) -> bool:
        if process.get("department") not in self.departments:
            return False

        modality_raw = process.get("modality", "")
        modality_normalized = self.normalize_text(modality_raw)
        if not any(kw in modality_normalized for kw in self.modalidad_keywords):
            return False

        if process.get("unspsc_code") in self.unspsc_codes:
            logger.info("match_unspsc", process_id=process["id"], code=process.get("unspsc_code"))
            return True

        name_upper = process.get("name", "").upper()
        desc_upper = process.get("description", "").upper()

        for kw in self.keywords:
            if kw in name_upper or kw in desc_upper:
                logger.info("match_keyword", process_id=process["id"], keyword=kw)
                return True

        for kw in self.certification_keywords:
            if kw in name_upper or kw in desc_upper:
                logger.info("match_certification", process_id=process["id"], keyword=kw)
                return True

        return False

    def detect_certifications(self, process: Dict) -> Dict:
        name_upper = process.get("name", "").upper()
        desc_upper = process.get("description", "").upper()
        text = f"{name_upper} {desc_upper}"

        return {
            "favorece_mujer_lider": any(kw in text for kw in ["MUJER LIDER", "MUJER LÍDER", "EMPRESA DE MUJERES"]),
            "favorece_pyme": any(kw in text for kw in ["PYME", "PEQUEÑA EMPRESA", "MICROEMPRESA"]),
            "requiere_equidad_genero": any(kw in text for kw in ["EQUIDAD DE GENERO", "EQUIDAD DE GÉNERO", "GENERO", "GÉNERO"]),
        }

    def filter_batch(self, processes: List[Dict]) -> List[Dict]:
        matched = [p for p in processes if self.matches(p)]
        logger.info("filter_complete", total=len(processes), matched=len(matched))
        return matched


def load_config(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
