import os
from typing import List
from langchain_unstructured import UnstructuredLoader
from langchain_core.documents import Document

class DocumentLoaderService:
    """
    用于从各种文件类型加载文档的服务。
    """

    def load_document(self, file_path: str) -> List[Document]:
        """
        从文件加载文档。

        Args:
            file_path (str): 文件路径。

        Returns:
            List[Document]: 文档列表。
        """
        loader = UnstructuredLoader(file_path)
        return loader.load()

document_loader_service = DocumentLoaderService()
