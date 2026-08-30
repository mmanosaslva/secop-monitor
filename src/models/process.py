from dataclasses import dataclass
from typing import Optional


@dataclass
class Process:
    id: str
    entity_name: str
    entity_nit: str
    department: str
    city: str
    name: str
    description: str
    status: str
    phase: str
    contract_type: str
    modality: str
    base_price: float
    publication_date: Optional[str]
    deadline: Optional[str]
    unspsc_code: str
    url: str


@dataclass
class Notification:
    process_id: str
    channel: str
    status: str
    error_message: Optional[str] = None
