import json
from typing import List, Dict
import structlog

logger = structlog.get_logger()


class FilterEngine:
    def __init__(self, config: Dict):
        self.departments = config.get("departments", [])
        self.keywords = [kw.upper() for kw in config.get("keywords", [])]
        self.unspsc_codes = config.get("unspsc_codes", [])

    def matches(self, process: Dict) -> bool:
        if process.get("department") not in self.departments:
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

        return False

    def filter_batch(self, processes: List[Dict]) -> List[Dict]:
        matched = [p for p in processes if self.matches(p)]
        logger.info("filter_complete", total=len(processes), matched=len(matched))
        return matched


def load_config(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
