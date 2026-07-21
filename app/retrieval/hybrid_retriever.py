from typing import List, Any, Dict, Tuple
from app.retrieval.base import BaseRetriever
from app.retrieval.vector_retriever import VectorRetriever
from app.retrieval.keyword_retriever import KeywordRetriever

class HybridRetriever(BaseRetriever):

    def __init__(
        self,
        collection_name: str,
        k: int = 8,
        vector_weight: float = 0.5,
        bm25_weight: float = 0.5,
        rrf_k: int = 60
    ):
        self.collection_name = collection_name
        self.k = k
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight
        self.rrf_k = rrf_k
        self.vector_retriever = VectorRetriever(collection_name, k * 2)
        self.keyword_retriever = KeywordRetriever(collection_name, k * 2)

    def _rrf_fusion(
        self,
        vector_results: List[Any],
        bm25_results: List[Any]
    ) -> List[Tuple[Any, float]]:
        doc_scores: Dict[int, Tuple[Any, float]] = {}
        for rank, doc in enumerate(vector_results):
            doc_hash = hash(doc.page_content)
            if doc_hash not in doc_scores:
                doc_scores[doc_hash] = (doc, 0.0)
            current_score = doc_scores[doc_hash][1]
            doc_scores[doc_hash] = (doc, current_score + self.vector_weight / (self.rrf_k + rank + 1))
        for rank, doc in enumerate(bm25_results):
            doc_hash = hash(doc.page_content)
            if doc_hash not in doc_scores:
                doc_scores[doc_hash] = (doc, 0.0)
            current_score = doc_scores[doc_hash][1]
            doc_scores[doc_hash] = (doc, current_score + self.bm25_weight / (self.rrf_k + rank + 1))
        sorted_docs = sorted(doc_scores.values(), key=lambda x: x[1], reverse=True)
        return sorted_docs

    def search(self, query: str, k: int = None, **kwargs) -> List[Any]:
        if k is None:
            k = self.k
        vector_results = self.vector_retriever.search(query, k=self.k * 2)
        bm25_results = self.keyword_retriever.search(query, k=self.k * 2)
        fused_results = self._rrf_fusion(vector_results, bm25_results)
        seen_contents = set()
        unique_results = []
        for doc, score in fused_results:
            doc_key = doc.page_content[:100] + doc.metadata.get("source", "")
            if doc_key not in seen_contents:
                seen_contents.add(doc_key)
                unique_results.append(doc)
        return unique_results[:k]
