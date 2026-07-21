import logging
import os
import re
from typing import Any, Dict, List

import pandas as pd
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


logger = logging.getLogger(__name__)


class TextSplitterService:
    """提供通用文档分块与 Excel 按行拆分能力的服务。

    - split_excel: 将 Excel 每一行转换为一个 Document，适用于错误码、费率表等结构化检索。
    - split_documents: 对已有的 Document 列表做递归字符分块，控制块大小与重叠。
    """

    def __init__(self) -> None:
        # 语义单元切片参数（优化方案A）
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=600,
            chunk_overlap=120,
            separators=["# ", "\n## ", "\n### ", "Q:", "A:", "描述：", "解决方案：", "\n\n", "\n", "。", "！", "？", " "]
        )

    @staticmethod
    def _sanitize_metadata(meta: Dict[str, Any]) -> Dict[str, Any]:
        """将 metadata 规范为 Milvus 可接受的标量类型。

        - 允许: str, int, float, bool
        - 其他类型: 转换为 str 表示
        - None: 丢弃
        """
        sanitized: Dict[str, Any] = {}
        for k, v in (meta or {}).items():
            if v is None:
                continue
            if isinstance(v, (str, int, float, bool)):
                sanitized[k] = v
                continue
            # 将 list/dict/其他对象安全转换为字符串
            try:
                sanitized[k] = str(v)
            except Exception:  # noqa: BLE001
                sanitized[k] = ""
        # 保证关键字段存在，避免后续批次缺失字段导致插入报错
        # 一些解析器（如 unstructured）可能为部分块提供特定字段，导致集合建立该字段后续批次缺失时报错
        # 统一补齐所有已知字段的默认值（空字符串），避免 DataNotMatchException
        if "languages" not in sanitized:
            sanitized["languages"] = ""
        if "source" not in sanitized:
            sanitized["source"] = ""
        if "coordinates" not in sanitized:
            sanitized["coordinates"] = ""
        if "file_directory" not in sanitized:
            sanitized["file_directory"] = ""
        if "filename" not in sanitized:
            sanitized["filename"] = ""
        if "last_modified" not in sanitized:
            sanitized["last_modified"] = ""
        if "page_number" not in sanitized:
            sanitized["page_number"] = 1
        if "filetype" not in sanitized:
            sanitized["filetype"] = ""
        if "category" not in sanitized:
            sanitized["category"] = ""
        if "element_id" not in sanitized:
            sanitized["element_id"] = ""
        if "doc_type" not in sanitized:
            sanitized["doc_type"] = ""
        if "keywords" not in sanitized:
            sanitized["keywords"] = ""
        if "section_title" not in sanitized:
            sanitized["section_title"] = ""
        return sanitized

    def split_excel(self, file_path: str) -> List[Document]:
        """按行拆分 Excel，逐行生成 Document。

        Args:
            file_path: Excel 文件路径（.xlsx/.xls）。

        Returns:
            List[Document]: 每一行一个 Document，metadata 包含行号与列名。
        """
        if not os.path.exists(file_path):
            msg = f"Excel 文件不存在: {file_path}"
            logger.error(msg)
            raise FileNotFoundError(msg)

        try:
            df = pd.read_excel(file_path, dtype=str)
        except Exception as exc:  # noqa: BLE001
            logger.error("读取 Excel 失败: %s", exc)
            raise

        documents: List[Document] = []
        # 将 NaN 转为空字符串，便于连接
        df = df.fillna("")
        columns = list(df.columns)

        for idx, row in df.iterrows():
            # 将一行各列拼接为一段可检索文本
            cells = [str(row[col]) for col in columns]
            # 使用 tab 分隔，兼顾结构化可读性
            text = "\t".join(cells).strip()
            if not text:
                continue
            meta = {
                "source": os.path.basename(file_path),
                "row_index": int(idx),
                # 列名列表转为可索引的字符串，避免列表类型导致 Milvus 报错
                "columns": "|".join(columns),
            }
            documents.append(Document(page_content=text, metadata=self._sanitize_metadata(meta)))

        logger.info("Excel 行拆分完成，共生成 %d 个文档块", len(documents))
        return documents

    def split_documents(self, documents: List[Document]) -> List[Document]:
        """对 Document 进行通用文本分块。

        Args:
            documents: 原始文档列表。

        Returns:
            List[Document]: 分块后的文档列表。
        """
        if not documents:
            return []

        # 仅对 page_content 非空的文档进行分块
        to_split = [d for d in documents if (d.page_content or "").strip()]
        if not to_split:
            return []

        chunks = self._splitter.split_documents(to_split)
        # 规范化分块后的 metadata，移除/转换不被 Milvus 接受的类型
        normalized: List[Document] = []
        for d in chunks:
            normalized.append(Document(page_content=d.page_content, metadata=self._sanitize_metadata(d.metadata)))
        logger.info("通用文本分块完成：输入 %d 篇，输出 %d 块", len(to_split), len(normalized))
        return normalized

    def split_txt_sections(self, file_path: str) -> List[Document]:
        """按 Markdown 风格标题（以#开头）将 txt 文本分段，并识别文档类型。

        规则：
            - 匹配以 `#` 开头的标题行（允许一个或多个 `#`，标题文本可紧随或空格后跟随）。
            - 标题行到下一个标题行（不含）视为一个段落（包含标题本身）。
            - 若文件开头没有标题，则在遇到首个标题前的内容视为一段（标题为空）。
            - 自动识别文档类型（FAQ/API/ERROR/GUIDE）并添加元数据。

        Args:
            file_path: 纯文本文件路径（.txt）。

        Returns:
            List[Document]: 每一段生成一个 Document，包含标题与段落文本及增强元数据。
        """
        if not os.path.exists(file_path):
            msg = f"TXT 文件不存在: {file_path}"
            logger.error(msg)
            raise FileNotFoundError(msg)

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            lines = content.splitlines()

        # 识别文档类型
        filename = os.path.basename(file_path).lower()
        doc_type = "GUIDE"
        category = "其他"
        
        if "faq" in filename or "问答" in filename:
            doc_type = "FAQ"
            category = "常见问题"
        elif "错误码" in filename or "error" in filename:
            doc_type = "ERROR"
            category = "错误处理"
        elif any(kw in filename for kw in ["接口", "api", "创建", "查询", "webhook"]):
            doc_type = "API"
            if "支付" in filename:
                category = "支付接口"
            elif "退款" in filename:
                category = "退款接口"
            elif "查询" in filename:
                category = "查询接口"
            elif "webhook" in filename:
                category = "回调通知"
            else:
                category = "API文档"
        elif "接入" in filename or "准备" in filename:
            doc_type = "GUIDE"
            category = "接入指南"

        header_pattern = re.compile(r"^\s*#+\s*.*")
        sections: List[Dict[str, Any]] = []
        current_title: str = ""
        current_lines: List[str] = []

        def flush_section() -> None:
            if not current_lines and not current_title:
                return
            body = "\n".join(current_lines).strip()
            # 段落文本包含标题行
            text_parts = []
            if current_title:
                text_parts.append(current_title)
            if body:
                text_parts.append(body)
            full_text = "\n".join(text_parts).strip()
            
            # 提取关键词
            keywords = []
            title_clean = current_title.lstrip("# ").strip()
            if title_clean:
                keywords.append(title_clean)
            
            sections.append({
                "title": title_clean,
                "text": full_text,
                "keywords": keywords,
            })

        for line in lines:
            if header_pattern.match(line):
                # 遇到新标题，先刷新上一段
                flush_section()
                current_title = line.strip()
                current_lines = []
            else:
                current_lines.append(line)

        # 文件尾巴刷新
        flush_section()

        documents: List[Document] = []
        for idx, sec in enumerate(sections):
            meta = {
                "source": os.path.basename(file_path) or "",
                "section_title": sec.get("title") or "",
                "section_index": int(idx),
                "file_type": "txt",
                "doc_type": doc_type,
                "category": category,
                "keywords": "|".join(sec.get("keywords", [])),
            }
            documents.append(Document(page_content=sec.get("text") or "", metadata=self._sanitize_metadata(meta)))

        logger.info("TXT 分段完成：共生成 %d 段，文档类型：%s", len(documents), doc_type)
        return documents


text_splitter_service = TextSplitterService()




