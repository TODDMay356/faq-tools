import shutil
import re
import time
from fastapi import APIRouter, UploadFile, File, Form, Body
from pydantic import BaseModel
from app.services.rag_service import rag_service
import os
from typing import Optional
from pathlib import Path

router = APIRouter()


class KnowledgeItem(BaseModel):
    """随时补充知识库的单条内容"""
    title: str
    content: str
    collection_name: str = "RAG"

# 定义文件上传目录（项目根目录下的 data 目录）
BASE_DIR = Path(__file__).resolve().parents[2]  # app/api/files.py -> app -> 项目根目录
UPLOAD_DIRECTORY = BASE_DIR / "data" / "uploads"
# 如果目录不存在，则创建它
UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
print(f"上传目录: {UPLOAD_DIRECTORY}")

@router.post("/upload")
async def upload_file(collection_name: str = Form(...), file: UploadFile = File(...)):
    """
    上传文件并将其摄取到向量存储中。

    Args:
        collection_name (str): 集合名称。
        file (UploadFile): 上传的文件。
    """
    file_path = os.path.join(UPLOAD_DIRECTORY, file.filename)
    # 将上传的文件保存到服务器
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 调用 RAG 服务处理文件
    rag_service.ingest_document(file_path, collection_name)

    return {"filename": file.filename, "collection_name": collection_name, "message": "File uploaded and processed successfully."}

@router.post("/add-knowledge")
async def add_knowledge(item: KnowledgeItem):
    """随时补充知识库：追加一条文本/问答并立即摄取到向量库。

    内容会以 Markdown 小节形式落盘到 data/uploads/RAG/ 下，
    既进入向量检索，也保留原文便于后续统一 reingest。

    Body 示例:
        {"title": "如何申请退款", "content": "在商户后台...", "collection_name": "RAG"}
    """
    title = item.title.strip()
    content = item.content.strip()
    if not title or not content:
        return {"error": "title 和 content 均不能为空"}

    rag_dir = UPLOAD_DIRECTORY / "RAG"
    rag_dir.mkdir(parents=True, exist_ok=True)

    # 文件名用标题做安全化处理，避免非法字符
    safe_title = re.sub(r"[^\w一-鿿-]+", "_", title).strip("_") or "knowledge"
    file_path = rag_dir / f"kb_{safe_title}_{int(time.time())}.txt"

    # 以「## 标题 + 正文」的小节格式写入，契合 txt 分节切片策略
    file_path.write_text(f"## {title}\n\n{content}\n", encoding="utf-8")

    try:
        rag_service.ingest_document(str(file_path), item.collection_name)
    except Exception as exc:  # noqa: BLE001
        return {"error": f"摄取失败: {exc}", "file": file_path.name}

    return {
        "message": "知识已补充并摄取成功",
        "title": title,
        "file": file_path.name,
        "collection_name": item.collection_name,
    }


@router.post("/batch-ingest")
async def batch_ingest_files(
    collection_name: str = Form(...),
    dir_path: Optional[str] = Form(None)
):
    """
    批量读取目录下的所有支持文件，并写入指定向量库集合。

    Args:
        collection_name (str): 向量库集合名。
        dir_path (Optional[str]): 目标文件夹路径，默认 ./data/uploads/RAG。

    Returns:
        dict: 各文件处理情况与总数。
    """
    import glob

    default_dir =  UPLOAD_DIRECTORY / "RAG"
    input_dir = dir_path or default_dir
    if not os.path.isdir(input_dir):
        return {"error": f"目录不存在: {input_dir}"}

    # 支持的文件后缀
    support_exts = [".txt", ".md", ".xlsx", ".pdf"]
    res = []
    files = [
        f for f in glob.glob(os.path.join(input_dir, "*"))
        if os.path.isfile(f) and os.path.splitext(f)[1].lower() in support_exts
    ]
    success_count = 0

    for fpath in files:
        fname = os.path.basename(fpath)
        try:
            rag_service.ingest_document(fpath, collection_name)
            res.append({"filename": fname, "status": "ok"})
            success_count += 1
        except Exception as e:
            res.append({"filename": fname, "status": "fail", "reason": str(e)})

    return {
        "files_total": len(files),
        "succeed": success_count,
        "failed": len(files) - success_count,
        "detail": res
    }
