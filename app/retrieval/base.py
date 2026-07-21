from abc import ABC, abstractmethod
from typing import List, Any, Dict

class BaseRetriever(ABC):
    

    @abstractmethod
    def search(self, query: str, k: int = 4, **kwargs) -> List[Any]:
        pass

    def _extract_metadata(self, doc: Any) -> Dict[str, Any]:
        if hasattr(doc, 'metadata'):
            return doc.metadata
        return {}
