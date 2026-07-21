from typing import List, Any
from app.retrieval.base import BaseRetriever

class VectorRetriever(BaseRetriever):
    def __init__(self, collection_name: str, k: int = 4):
        self.collection_name = collection_name
        self.k = k
        self._vector_store = None

    @property
    def vector_store(self):
        if self._vector_store is None:
            from app.services.vector_store_service import vector_store_service
            self._vector_store = vector_store_service.get_vector_store(self.collection_name)
        return self._vector_store

    def search(self, query: str, k: int = None, **kwargs) -> List[Any]:
        if k is None:
            k = self.k
        docs = self.vector_store.similarity_search(query, k=k)
        return docs
