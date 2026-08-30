from abc import ABC, abstractmethod
from typing import Dict


class NotificationChannel(ABC):
    @abstractmethod
    def send(self, process: Dict, recipient: str) -> bool:
        pass
