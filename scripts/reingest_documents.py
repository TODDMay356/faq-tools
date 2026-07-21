"""文档重新摄取脚本：清除集合并重新处理所有文档"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import glob
import os
from app.services.rag_service import rag_service
from app.services.vector_store_service import vector_store_service
from app.core.config import settings

def reingest_documents(collection_name: str, dir_path: str = None):
    """清除集合并重新摄取文档
    
    Args:
        collection_name: 集合名称
        dir_path: 文档目录路径，默认为 data/uploads/RAG
    """
    # 默认目录
    if not dir_path:
        dir_path = project_root / "data" / "uploads" / "RAG"
    else:
        dir_path = Path(dir_path)
    
    if not dir_path.exists():
        print(f"错误：目录不存在 {dir_path}")
        return
    
    print(f"开始处理集合: {collection_name}")
    print(f"文档目录: {dir_path}")
    
    # 1. 清除集合
    print("\n步骤1: 清除现有集合数据...")
    try:
        vector_store_service.client.delete_collection("RAG")
        vector_store_service.client.delete_collection(collection_name)
        print(f"✓ 集合 '{collection_name}' 已清除")
    except Exception as e:
        print(f"清除集合时出错（可能不存在）: {e}")
    
    # 2. 扫描文件
    print("\n步骤2: 扫描文档文件...")
    support_exts = [".txt", ".md", ".xlsx", ".pdf"]
    files = [
        f for f in glob.glob(str(dir_path / "*"))
        if os.path.isfile(f) and os.path.splitext(f)[1].lower() in support_exts
    ]
    
    print(f"找到 {len(files)} 个文件")
    
    # 3. 处理文件
    print("\n步骤3: 处理文档...")
    success_count = 0
    failed_files = []
    
    for idx, fpath in enumerate(files, 1):
        fname = os.path.basename(fpath)
        print(f"[{idx}/{len(files)}] 处理: {fname}")
        try:
            rag_service.ingest_document(fpath, collection_name)
            success_count += 1
            print(f"  ✓ 成功")
        except Exception as e:
            print(f"  ✗ 失败: {e}")
            failed_files.append((fname, str(e)))
    
    # 4. 输出结果
    print("\n" + "="*60)
    print(f"处理完成！")
    print(f"总文件数: {len(files)}")
    print(f"成功: {success_count}")
    print(f"失败: {len(failed_files)}")
    
    if failed_files:
        print("\n失败文件列表:")
        for fname, error in failed_files:
            print(f"  - {fname}: {error}")


if __name__ == "__main__":
    # 默认参数
    collection = settings.default_collection_name
    directory = None
    
    # 支持命令行参数
    if len(sys.argv) > 1:
        collection = sys.argv[1]
    if len(sys.argv) > 2:
        directory = sys.argv[2]
    
    reingest_documents(collection, directory)
