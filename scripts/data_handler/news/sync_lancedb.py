import os
import sys

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from app.core.database import get_mongo_db_sync
from tradingagents.searcher.vector_store import VectorStore


def sync_insight_news_to_lancedb():
    """将 MongoDB insight_news 集合的数据同步到 LanceDB"""

    # 1. 从 MongoDB 读取数据
    db = get_mongo_db_sync()
    mongo_collection = db["insight_news"]

    # 获取所有文档
    documents = list(mongo_collection.find())
    if not documents:
        print("MongoDB insight_news 集合中没有数据")
        return

    print(f"从 MongoDB 读取到 {len(documents)} 条数据")

    # 2. 准备 VectorStore 文档格式
    # content 字段作为 content，其余字段作为 metadata
    vector_docs = []
    for doc in documents:
        # 获取 content 字段
        content = doc.get("content", "")
        if not content:
            print(f"跳过无 content 的文档: _id={doc.get('_id')}")
            continue

        # 其余字段作为 metadata
        metadata = {k: v for k, v in doc.items() if k != "content"}

        # 处理 MongoDB 的 ObjectId，转换为字符串
        if "_id" in metadata:
            metadata["_id"] = str(metadata["_id"])

        # 使用 MongoDB 的 _id 作为 doc_id（如果存在）
        doc_id = str(doc.get("_id", ""))

        vector_docs.append({
            "id": doc_id,
            "content": content,
            "metadata": metadata,
        })

    if not vector_docs:
        print("没有有效的文档可以导入")
        return

    print(f"准备导入 {len(vector_docs)} 条文档到 LanceDB")

    # 3. 使用 VectorStore 批量插入
    store = VectorStore(collection_name="insight_news")
    ids = store.add_documents(vector_docs)

    print(f"成功导入 {len(ids)} 条数据到 LanceDB insight_news 集合")


if __name__ == "__main__":
    sync_insight_news_to_lancedb()
