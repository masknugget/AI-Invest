import os
import sys

from app.core.database import get_mongo_db_sync
from tradingagents.searcher.vector_store import VectorStore

db = get_mongo_db_sync()
mongo_collection = db["insight_agg"]

# 获取所有文档
documents = list(mongo_collection.find())

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
    metadata = {
        "article_id": doc.get("article_id"),
        "title": doc.get("title"),
        "language": doc.get("language"),
        "publish_time": doc.get('publish_time'),
    }

    # 处理 MongoDB 的 ObjectId，转换为字符串
    if "_id" in metadata:
        metadata["_id"] = str(metadata["_id"])

    search_content = doc.get("keywords")
    if isinstance(search_content, list):
        search_content = " ".join(search_content)

    # 使用 MongoDB 的 _id 作为 doc_id（如果存在）
    doc_id = str(doc.get("_id", ""))

    vector_docs.append({
        "id": doc_id,
        "content": search_content,
        "metadata": metadata,
    })

print(f"准备导入 {len(vector_docs)} 条文档到 LanceDB")
store = VectorStore(collection_name="insight_agg")
ids = store.add_documents(vector_docs)
