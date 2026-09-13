import unicodedata
import json
from typing import List, Dict
import structlog

logger = structlog.get_logger()


class FilterEngine:
    def __init__(self, config: Dict):
        self.departments = [self.normalize_text(d) for d in config.get("departments", [])]
        self.keywords = [self.normalize_text(kw) for kw in config.get("keywords", [])]
        self.unspsc_codes = config.get("unspsc_codes", [])
        self.certification_keywords = [self.normalize_text(kw) for kw in config.get("certification_keywords", [])]
        self.modalidad_keywords = [self.normalize_text(kw) for kw in config.get("modalidad_keywords", [])]

    def normalize_text(self, text: str) -> str:
        text = unicodedata.normalize('NFD', text)
        text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
        return text.lower().strip()

    def matches(self, process: Dict) -> bool:
        department = self.normalize_text(process.get("department", ""))
        if department not in self.departments:
            return False

        modality_raw = process.get("modality", "")
        modality_normalized = self.normalize_text(modality_raw)
        if not any(kw in modality_normalized for kw in self.modalidad_keywords):
            return False

        if process.get("unspsc_code") in self.unspsc_codes:
            logger.info("match_unspsc", process_id=process["id"], code=process.get("unspsc_code"))
            return True

        name_normalized = self.normalize_text(process.get("name", ""))
        desc_normalized = self.normalize_text(process.get("description", ""))

        for kw in self.keywords:
            if kw in name_normalized or kw in desc_normalized:
                logger.info("match_keyword", process_id=process["id"], keyword=kw)
                return True

        for kw in self.certification_keywords:
            if kw in name_normalized or kw in desc_normalized:
                logger.info("match_certification", process_id=process["id"], keyword=kw)
                return True

        return False

    def detect_certifications(self, process: Dict) -> Dict:
        name_normalized = self.normalize_text(process.get("name", ""))
        desc_normalized = self.normalize_text(process.get("description", ""))
        text = f"{name_normalized} {desc_normalized}"

        return {
            "favorece_mujer_lider": any(kw in text for kw in ["mujer lider", "empresa de mujeres"]),
            "favorece_pyme": any(kw in text for kw in ["pyme", "pequeña empresa", "microempresa"]),
            "requiere_equidad_genero": any(kw in text for kw in ["equidad de genero", "genero"]),
        }

    def filter_batch(self, processes: List[Dict]) -> List[Dict]:
        matched = [p for p in processes if self.matches(p)]
        logger.info("filter_complete", total=len(processes), matched=len(matched))
        return matched


def load_config(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
