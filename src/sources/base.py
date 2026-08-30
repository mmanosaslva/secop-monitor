from abc import ABC, abstractmethod
from typing import List, Dict


class DataSource(ABC):
    @abstractmethod
    def fetch_processes(self, **kwargs) -> List[Dict]:
        pass
