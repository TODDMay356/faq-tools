from typing import List, Any, Dict
import logging
import jieba
import rank_bm25
from app.retrieval.base import BaseRetriever

class KeywordRetriever(BaseRetriever):
    def __init__(self, collection_name: str, k: int = 4):
        self.collection_name = collection_name
        self.k = k
        self.vector_store = None
        self.documents = []
        self.tokenized_corpus = []
        self.bm25 = None

    def _ensure_initialized(self):
        if self.vector_store is None:
            from app.services.vector_store_service import vector_store_service
            self.vector_store = vector_store_service.get_vector_store(self.collection_name)
            self._initialize_bm25()

    def _initialize_bm25(self):
        collection = self.vector_store._collection
        results = collection.get(include=["documents", "metadatas"])
        if results and results.get("documents"):
            self.documents = []
            for i, doc_content in enumerate(results["documents"]):
                metadata = results["metadatas"][i] if results.get("metadatas") else {}
                from langchain_core.documents import Document
                doc = Document(page_content=doc_content, metadata=metadata)
                self.documents.append(doc)
            self.tokenized_corpus = [self._tokenize(doc.page_content) for doc in self.documents]
            self.bm25 = rank_bm25.BM25Okapi(self.tokenized_corpus)

    def _tokenize(self, text: str) -> List[str]:
        return list(jieba.cut(text))

    def search(self, query: str, k: int = None, **kwargs) -> List[Any]:
        if k is None:
            k = self.k
        self._ensure_initialized()
        if not self.tokenized_corpus:
            return []
        tokenized_query = self._tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)
        doc_scores = list(enumerate(scores))
        doc_scores.sort(key=lambda x: x[1], reverse=True)
        positive_indices = [idx for idx, score in doc_scores[:k * 2] if score > 0]
        if positive_indices:
            return [self.documents[idx] for idx in positive_indices[:k]]
        logger = logging.getLogger(__name__)
        logger.info("[KeywordRetriever] BM25 零匹配，返回 Top %d 结果", k)
        return [self.documents[idx] for idx, _ in doc_scores[:k]]
