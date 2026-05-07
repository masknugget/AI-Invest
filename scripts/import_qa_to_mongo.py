#!/usr/bin/env python3
"""
将 data_qa_5000.json 导入 MongoDB 的 qa_pair collection
支持重复运行（以 uuid 为唯一键进行 upsert）
"""

import json
import sys
from pathlib import Path

# 将项目根目录加入 sys.path，以便导入 app.core.config
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pymongo import MongoClient, UpdateOne
from app.core.config import settings


def main():
    input_path = PROJECT_ROOT / "scripts" / "data_local" / "data_qa_5000.json"

    print("=" * 60)
    print("开始导入 QA 数据到 MongoDB...")
    print(f"[数据文件] {input_path}")

    # 读取 JSON
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"[成功] 读取 JSON，共 {len(data)} 条记录")

    # 连接 MongoDB
    print(f"\n[连接] MongoDB: {settings.MONGODB_HOST}:{settings.MONGODB_PORT}")
    try:
        client = MongoClient(
            settings.MONGO_URI,
            maxPoolSize=settings.MONGO_MAX_CONNECTIONS,
            minPoolSize=settings.MONGO_MIN_CONNECTIONS,
            connectTimeoutMS=settings.MONGO_CONNECT_TIMEOUT_MS,
            socketTimeoutMS=settings.MONGO_SOCKET_TIMEOUT_MS,
            serverSelectionTimeoutMS=settings.MONGO_SERVER_SELECTION_TIMEOUT_MS,
        )
        client.admin.command("ping")
        db = client[settings.MONGO_DB]
        col = db["qa_pair"]
        print("[成功] MongoDB 连接成功")
        print(f"目标数据库: {settings.MONGO_DB}")
        print(f"目标集合: qa_pair")
    except Exception as e:
        print(f"[错误] MongoDB 连接失败: {e}")
        sys.exit(1)

    # 创建 uuid 唯一索引
    print("\n[索引] 正在检查索引...")
    existing_indexes = {idx["name"] for idx in col.list_indexes()}
    if "uuid_1" not in existing_indexes:
        col.create_index("uuid", unique=True)
        print("[成功] 已创建 uuid 唯一索引")
    else:
        print("[成功] uuid 唯一索引已存在")

    # 批量 upsert
    print(f"\n[写入] 正在写入数据，共 {len(data)} 条记录...")
    batch_size = 1000
    requests = []
    success_count = 0

    for i, item in enumerate(data):
        requests.append(
            UpdateOne(
                {"uuid": item["uuid"]},
                {"$set": item},
                upsert=True,
            )
        )

        if len(requests) >= batch_size:
            try:
                result = col.bulk_write(requests, ordered=False)
                success_count += result.upserted_count + result.modified_count
                print(f"[进度] 已处理 {i + 1}/{len(data)} 条记录")
                requests.clear()
            except Exception as e:
                print(f"[错误] 批量写入失败: {e}")
                requests.clear()

    # 处理剩余数据
    if requests:
        try:
            result = col.bulk_write(requests, ordered=False)
            success_count += result.upserted_count + result.modified_count
        except Exception as e:
            print(f"[错误] 最后批量写入失败: {e}")

    total_in_db = col.count_documents({})
    print(f"\n[完成] 导入完成!")
    print(f"[统计] 本次处理: {success_count} 条记录")
    print(f"[统计] 集合总记录数: {total_in_db}")
    print("=" * 60)

    client.close()


if __name__ == "__main__":
    main()
