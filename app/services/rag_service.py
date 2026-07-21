from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.services.document_loader_service import document_loader_service
from app.services.text_splitter_service import text_splitter_service
from app.services.vector_store_service import vector_store_service
from app.services.llm_service import llm_service
from app.retrieval import HybridRetriever, Reranker, IntentType
from app.core.config import settings
from app.prompts import RAG_PROMPT, INTENT_PROMPT, QUERY_EXPANSION_PROMPT
import os
import time
import logging
from typing import List, Dict, Any, Optional

class RAGService:
    def ingest_document(self, file_path: str, collection_name: str):
        file_extension = os.path.splitext(file_path)[1].lower()
        if file_extension == ".xlsx":
            documents = text_splitter_service.split_excel(file_path)
        elif file_extension == ".txt":
            documents = text_splitter_service.split_txt_sections(file_path)
        else:
            documents = document_loader_service.load_document(file_path)
            documents = text_splitter_service.split_documents(documents)

        vector_store = vector_store_service.get_vector_store(collection_name)

        batch_size_env = os.getenv("MILVUS_INSERT_BATCH_SIZE", "128").strip()
        try:
            batch_size = max(1, int(batch_size_env))
        except ValueError:
            batch_size = 128

        total = len(documents)
        inserted = 0
        logger = logging.getLogger(__name__)

        for start in range(0, total, batch_size):
            end = min(start + batch_size, total)
            batch = documents[start:end]
            attempt_batch_size = len(batch)
            while True:
                try:
                    vector_store.add_documents(batch[:attempt_batch_size])
                    inserted += attempt_batch_size
                    break
                except Exception as exc:
                    msg = str(exc).lower()
                    if "memory quota exhausted" in msg and attempt_batch_size > 1:
                        attempt_batch_size = max(1, attempt_batch_size // 2)
                        time.sleep(0.2)
                        continue
                    raise
        print(f"成功将 {inserted}/{total} 个文档块摄取到集合 '{collection_name}' 中。")

    def _classify_intent(self, query: str) -> IntentType:
        reranker = Reranker()
        return reranker.classify_intent(query)

    def _expand_query(self, query: str, intent: IntentType) -> List[str]:
        logger = logging.getLogger(__name__)
        intent_prompts = {
            IntentType.ERROR_CODE: "重点关注错误码、错误信息、解决方法相关的表达。",
            IntentType.API_USAGE: "重点关注API接口、参数、返回值、调用方式相关的表达。",
            IntentType.FAQ: "重点关注常见问题、解决方案、操作步骤相关的表达。",
            IntentType.POLICY: "重点关注政策规则、费率标准、结算周期、限额要求相关的表达。",
            IntentType.GENERAL: "关注问题的核心概念和不同表述方式。",
        }
        context_hint = intent_prompts.get(intent, "")

        try:
            prompt = PromptTemplate.from_template(QUERY_EXPANSION_PROMPT)
            chain = prompt | llm_service.llm | StrOutputParser()
            result = chain.invoke({
                "question": query,
                "intent_context": context_hint
            })
            queries = [q.strip() for q in result.strip().split('\n') if q.strip()]
            queries = [query] + queries
            logger.info("[RAG] 意图=%s，生成 %d 个查询变体", intent.value, len(queries))
            return queries[:8]
        except Exception as e:
            logger.warning("[RAG] 查询扩展失败: %s，使用原始问题", e)
            return [query]

    def _hybrid_retrieve(self, queries: List[str], collection_name: str, k: int = 8) -> List[Any]:
        logger = logging.getLogger(__name__)
        hybrid_retriever = HybridRetriever(collection_name, k=k * 2)

        all_docs = []
        seen_contents = set()

        for query in queries:
            try:
                docs = hybrid_retriever.search(query, k=k * 2)
                for doc in docs:
                    doc_id = f"{doc.page_content[:100]}_{doc.metadata.get('source', '')}"
                    if doc_id not in seen_contents:
                        seen_contents.add(doc_id)
                        all_docs.append(doc)
            except Exception as e:
                logger.warning("[RAG] 查询 '%s' 检索失败: %s", query[:50], e)
                continue

        logger.info("[RAG] 混合检索去重后获得 %d 个文档", len(all_docs))
        return all_docs

    def _rerank_documents(
        self,
        docs: List[Any],
        query: str,
        intent: IntentType,
        top_k: int = 4
    ) -> List[Any]:
        logger = logging.getLogger(__name__)
        if len(docs) <= top_k:
            return docs

        use_cross_encoder = os.getenv("USE_CROSS_ENCODER", "false").lower() == "true"
        reranker = Reranker(use_cross_encoder=use_cross_encoder)
        reranked = reranker.rerank(query, docs, top_k=top_k, intent=intent)

        logger.info("[RAG] 重排序后保留 Top %d 文档", len(reranked))
        return reranked

    def answer_question(self, question: str, collection_name: str) -> str:
        logger = logging.getLogger(__name__)
        logger.info("[RAG] 开始处理问题: %s", question[:100])

        intent = self._classify_intent(question)
        logger.info("[RAG] 识别意图: %s", intent.value)

        queries = self._expand_query(question, intent)

        all_docs = self._hybrid_retrieve(queries, collection_name, k=8)

        retrieved_docs = self._rerank_documents(all_docs, question, intent, top_k=4)

        logger.info("[RAG] 最终检索到 %d 个相关文档", len(retrieved_docs))
        for idx, doc in enumerate(retrieved_docs, 1):
            logger.info("[RAG] 文档 %d: 来源=%s, 类型=%s, 标题=%s",
                idx,
                doc.metadata.get("source", "未知"),
                doc.metadata.get("doc_type", "未知"),
                doc.metadata.get("section_title", "无"))

        context = "\n\n".join(doc.page_content for doc in retrieved_docs)

        intent_instructions = {
            IntentType.ERROR_CODE: "这是一个错误码查询。请优先引用相关错误码文档，解释错误原因和解决方法。",
            IntentType.API_USAGE: "这是一个API使用问题。请详细说明接口调用方式、参数含义和返回值。",
            IntentType.FAQ: "这是一个常见问题。请给出清晰的操作步骤或解决方案。",
            IntentType.POLICY: "这是一个政策规则问题。请准确引用相关政策条款。",
            IntentType.GENERAL: "请根据上下文信息给出准确的回答。",
        }
        instruction = intent_instructions.get(intent, "")

        prompt = PromptTemplate.from_template(RAG_PROMPT)
        result_prompt = prompt.invoke({
            "context": context,
            "question": question,
            "intent_instruction": instruction
        })

        logger.info("[RAG] 开始生成答案...")
        result = (prompt | llm_service.llm | StrOutputParser()).invoke({
            "context": context,
            "question": question,
            "intent_instruction": instruction
        })
        logger.info("[RAG] 答案生成完成，长度: %d 字符", len(result))
        return result


rag_service = RAGService()
