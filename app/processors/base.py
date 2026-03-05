# app/processors/base.py
from abc import ABC, abstractmethod

class BaseFileProcessor(ABC):
    @abstractmethod
    async def process(self, file_doc: dict) -> dict:
        """
        Process file and return:
        {
            "status": "completed",
            "visits": [{"dos": str, "start_page": int, "end_page": int, "confidence": float}],
            "avg_confidence": float
        }
        """
        pass