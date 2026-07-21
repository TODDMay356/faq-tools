import os

# 必须在导入 HuggingFaceEmbeddings 之前设置环境变量
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_ENDPOINT"] = "https://hf-mirror.com"

import chromadb
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from app.core.config import settings


class VectorStoreService:
    """用于与 ChromaDB 向量数据库交互的服务"""

    def __init__(self) -> None:
        self.embeddings = HuggingFaceEmbeddings(model_name=settings.embedding_model_name)
        self.client = chromadb.HttpClient(
            host=settings.chroma_host,
            port=int(settings.chroma_port)
        )
        print(f"连接到 ChromaDB 服务器: {settings.chroma_host}:{settings.chroma_port}")

    def get_vector_store(self, collection_name: str):
        """返回 ChromaDB 向量存储实例"""
        return Chroma(
            collection_name=collection_name,
            embedding_function=self.embeddings,
            client=self.client,
        )


vector_store_service = VectorStoreService()
