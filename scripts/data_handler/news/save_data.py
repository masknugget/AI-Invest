import os
import sys
import json

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

documents = [{k: v for k, v in doc.items() if k != "_id"} for doc in documents]
output_path = r"F:\project_work\hf\AI-Invest\mock\documents.json"
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(documents, f, ensure_ascii=False, indent=2)

print(f"已保存 {len(documents)} 条文档到 {output_path}")

with open(output_path, 'r', encoding='utf-8') as f:
    documents = json.load(f)

print(f"加载了 {len(documents)} 条文档")
print(documents[0])
