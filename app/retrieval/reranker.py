from enum import Enum
from typing import List, Any, Optional, Tuple
import logging
import numpy as np

class IntentType(Enum):
    ERROR_CODE = "ERROR_CODE"
    API_USAGE = "API_USAGE"
    FAQ = "FAQ"
    POLICY = "POLICY"
    GENERAL = "GENERAL"

class Reranker:
    def __init__(
        self,
        use_cross_encoder: bool = False,
        cross_encoder_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    ):
        self.use_cross_encoder = use_cross_encoder
        self.cross_encoder_model = cross_encoder_model
        self.cross_encoder = None
        self.embeddings = None
        self.logger = logging.getLogger(__name__)
        if self.use_cross_encoder:
            self._init_cross_encoder()
        else:
            self._init_embeddings()

    def _init_cross_encoder(self):
        try:
            from sentence_transformers import CrossEncoder
            self.cross_encoder = CrossEncoder(self.cross_encoder_model)
            self.logger.info("Cross-Encoder 重排序已启用")
        except ImportError:
            self.logger.warning("sentence_transformers 未安装，Cross-Encoder 重排将不可用，使用 embedding 余弦相似度")
            self.use_cross_encoder = False
            self._init_embeddings()

    def _init_embeddings(self):
        try:
            from app.services.vector_store_service import vector_store_service
            self.embeddings = vector_store_service.embeddings
            self.logger.info("Embedding 余弦相似度排序已启用")
        except Exception as e:
            self.logger.warning("无法加载 embedding 模型: %s", e)
            self.embeddings = None

    def _compute_embedding_similarity(self, query: str, docs: List[Any]) -> List[float]:
        if self.embeddings is None:
            return [0.0] * len(docs)
        try:
            query_embedding = self.embeddings.embed_query(query)
            doc_embeddings = self.embeddings.embed_documents([doc.page_content for doc in docs])
            similarities = []
            for doc_emb in doc_embeddings:
                sim = self._cosine_similarity(query_embedding, doc_emb)
                similarities.append(sim)
            return similarities
        except Exception as e:
            self.logger.warning("Embedding 相似度计算失败: %s", e)
            return [0.0] * len(docs)

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(vec1, vec2) / (norm1 * norm2))

    def classify_intent(self, query: str) -> IntentType:
        import re
        query_lower = query.lower()
        if re.search(r'(E\d{3,4}|错误|error\s*code|err\d+|状态码|报错)', query_lower):
            return IntentType.ERROR_CODE
        elif re.search(r'(api|接口|调用|请求|参数|回调|webhook|request|method|地址|url|endpoint|生产|测试)', query_lower):
            return IntentType.API_USAGE
        elif re.search(r'(faq|如何|怎么|怎样|能不能|是否|可以|有没有)', query_lower):
            return IntentType.FAQ
        elif re.search(r'(政策|规则|费率|结算|限额|风控|周期|标准)', query_lower):
            return IntentType.POLICY
        return IntentType.GENERAL

    def _semantic_rerank(
        self,
        docs: List[Any],
        query: str,
        intent: Optional[IntentType] = None
    ) -> List[Tuple[Any, float]]:
        if not docs:
            return []
        if self.use_cross_encoder and self.cross_encoder:
            doc_texts = [doc.page_content for doc in docs]
            pairs = [[query, doc_text] for doc_text in doc_texts]
            scores = self.cross_encoder.predict(pairs)
            return list(zip(docs, scores))
        else:
            similarities = self._compute_embedding_similarity(query, docs)
            return list(zip(docs, similarities))

    def _boost_by_metadata(
        self,
        doc_scores: List[Tuple[Any, float]],
        intent: IntentType
    ) -> List[Tuple[Any, float]]:
        doc_type_boost = {
            IntentType.ERROR_CODE: "ERROR",
            IntentType.API_USAGE: "API",
            IntentType.FAQ: "FAQ",
            IntentType.POLICY: "POLICY",
        }
        boost_type = doc_type_boost.get(intent, "")
        if not boost_type:
            return doc_scores
        boosted = []
        for doc, semantic_score in doc_scores:
            metadata = doc.metadata
            doc_type = metadata.get("doc_type", "")
            boost = 0.0
            if boost_type in doc_type.upper():
                boost = 0.5
            boosted.append((doc, semantic_score + boost))
        return boosted

    def rerank(
        self,
        query: str,
        docs: List[Any],
        top_k: int = 4,
        intent: Optional[IntentType] = None
    ) -> List[Any]:
        if len(docs) <= top_k:
            return docs
        if intent is None:
            intent = self.classify_intent(query)
        doc_scores = self._semantic_rerank(docs, query, intent)
        doc_scores = self._boost_by_metadata(doc_scores, intent)
        doc_scores.sort(key=lambda x: x[1], reverse=True)
        return [doc for doc, _ in doc_scores[:top_k]]


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(np.dot(vec1, vec2) / (norm1 * norm2))
