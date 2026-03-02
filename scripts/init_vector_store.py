"""
将 MongoDB 股票基础数据导入 VectorStore
用于初始化向量数据库，支持股票名称和代码的相似性查询

Usage:
    python scripts/init_vector_store.py
"""

import os
import sys

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from pymongo import MongoClient
from tradingagents.searcher import VectorStore


def init_stock_vector_store(
    mongo_uri="mongodb://localhost:27017",
    db_name="stock_db",
    collection_name="stock_daily_basic",
    vector_collection="stock_basic"
):
    """
    将 MongoDB 股票基础数据导入 VectorStore
    
    Args:
        mongo_uri: MongoDB 连接 URI
        db_name: 数据库名称
        collection_name: MongoDB collection 名称
        vector_collection: VectorStore collection 名称
    """
    print("=" * 60)
    print("开始初始化 VectorStore")
    print("=" * 60)
    
    # 1. 连接 MongoDB
    print(f"\n1. 连接 MongoDB: {mongo_uri}")
    try:
        client = MongoClient(mongo_uri)
        db = client[db_name]
        collection = db[collection_name]
        print(f"   ✅ 连接成功")
    except Exception as e:
        print(f"   ❌ 连接失败: {e}")
        return False
    
    # 2. 统计文档数量
    total_count = collection.count_documents({})
    print(f"\n2. MongoDB 文档统计")
    print(f"   数据库: {db_name}")
    print(f"   集合: {collection_name}")
    print(f"   文档总数: {total_count}")
    
    if total_count == 0:
        print("   ⚠️ 没有数据需要导入")
        return False
    
    # 3. 初始化 VectorStore
    print(f"\n3. 初始化 VectorStore")
    print(f"   集合名称: {vector_collection}")
    try:
        store = VectorStore(collection_name=vector_collection)
        print(f"   ✅ VectorStore 初始化成功")
    except Exception as e:
        print(f"   ❌ VectorStore 初始化失败: {e}")
        return False
    
    # 4. 导入数据
    print(f"\n4. 导入数据到 VectorStore")
    print(f"   正在处理...")
    
    # 注意: DashScope embedding API 限制每批最多 10 条
    # embed_documents 方法会自动处理分批，这里可以设置较大的 batch_size
    batch_size = 100
    inserted_count = 0
    skipped_count = 0
    
    # 获取所有文档（只取 name 和 symbol 字段）
    cursor = collection.find({}, {"name": 1, "symbol": 1, "_id": 0})
    
    batch = []
    for doc in cursor:
        name = doc.get("name", "").strip()
        symbol = doc.get("symbol", "").strip()
        
        # 跳过无效数据
        if not name or not symbol:
            skipped_count += 1
            continue
        
        # 组合成一行文本："股票名称 (股票代码)"
        content = f"{name} ({symbol})"
        
        # 构建文档
        document = {
            "id": f"stock_{symbol}",  # 使用 symbol 作为 ID
            "content": content,
            "metadata": {
                "name": name,
                "symbol": symbol,
                "source": "stock_daily_basic"
            }
        }
        batch.append(document)
        
        # 批量插入
        if len(batch) >= batch_size:
            try:
                store.add_documents(batch)
                inserted_count += len(batch)
                print(f"   已导入: {inserted_count}/{total_count}", end="\r")
                batch = []
            except Exception as e:
                print(f"\n   ❌ 批量导入失败: {e}")
                skipped_count += len(batch)
                batch = []
    
    # 处理剩余文档
    if batch:
        try:
            store.add_documents(batch)
            inserted_count += len(batch)
        except Exception as e:
            print(f"\n   ❌ 最后一批导入失败: {e}")
            skipped_count += len(batch)
    
    print(f"\n   ✅ 导入完成")
    print(f"   成功: {inserted_count}")
    print(f"   跳过: {skipped_count}")
    
    # 5. 验证
    print(f"\n5. 验证导入结果")
    final_count = store.count()
    print(f"   VectorStore 文档总数: {final_count}")
    
    # 6. 测试查询
    print(f"\n6. 测试查询")
    try:
        # 测试用例1: 按名称查询
        test_query = "平安银行"
        results = store.search(test_query, top_k=3)
        print(f"\n   查询: '{test_query}'")
        for i, r in enumerate(results, 1):
            print(f"   {i}. [{r.score:.3f}] {r.content}")
        
        # 测试用例2: 按代码查询
        test_query = "000001"
        results = store.search(test_query, top_k=3)
        print(f"\n   查询: '{test_query}'")
        for i, r in enumerate(results, 1):
            print(f"   {i}. [{r.score:.3f}] {r.content}")
            
    except Exception as e:
        print(f"   ⚠️ 查询测试失败: {e}")
    
    # 关闭连接
    client.close()
    
    print("\n" + "=" * 60)
    print("初始化完成！")
    print("=" * 60)
    
    return True


def clear_vector_store(collection_name="stock_basic"):
    """
    清空 VectorStore 中的股票数据
    
    Usage:
        python scripts/init_vector_store.py --clear
    """
    print(f"清空 VectorStore 集合: {collection_name}")
    try:
        store = VectorStore(collection_name=collection_name)
        store.clear()
        print("✅ 清空完成")
        return True
    except Exception as e:
        print(f"❌ 清空失败: {e}")
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="初始化 VectorStore 股票数据")
    parser.add_argument(
        "--clear",
        action="store_true",
        help="清空 VectorStore 数据"
    )
    parser.add_argument(
        "--mongo-uri",
        default="mongodb://localhost:27017",
        help="MongoDB URI (默认: mongodb://localhost:27017)"
    )
    parser.add_argument(
        "--collection",
        default="stock_basic",
        help="VectorStore 集合名称 (默认: stock_basic)"
    )
    
    args = parser.parse_args()
    
    if args.clear:
        clear_vector_store(args.collection)
    else:
        init_stock_vector_store(
            mongo_uri=args.mongo_uri,
            vector_collection=args.collection
        )
