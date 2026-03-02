"""
将 MongoDB 股票基础数据导入 BM25Store
用于初始化 BM25 索引，支持股票名称和代码的关键词搜索

Usage:
    python scripts/init_bm25_store.py
"""

import os
import sys

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from pymongo import MongoClient
from tradingagents.searcher import BM25Store

# 加载应用配置
from app.config.config import Config

DEFAULT_PERSIST_DIR = Config.bm25_persist_directory
DEFAULT_COLLECTION = Config.bm25_default_collection
DEFAULT_K1 = Config.bm25_k1
DEFAULT_B = Config.bm25_b
DEFAULT_DELTA = Config.bm25_delta
DEFAULT_METHOD = Config.bm25_method


def init_stock_bm25_store(
    mongo_uri="mongodb://localhost:27017",
    db_name="stock_db",
    collection_name="stock_daily_basic",
    bm25_collection=None,
    persist_directory=None,
    k1=None,
    b=None,
    delta=None,
    method=None
):
    """
    将 MongoDB 股票基础数据导入 BM25Store
    
    Args:
        mongo_uri: MongoDB 连接 URI
        db_name: 数据库名称
        collection_name: MongoDB collection 名称
        bm25_collection: BM25Store collection 名称，默认从配置读取
        persist_directory: BM25 数据持久化目录，默认从配置读取
        k1: BM25 k1 参数，默认从配置读取
        b: BM25 b 参数，默认从配置读取
        delta: BM25+ delta 参数，默认从配置读取
        method: BM25 计算方法，默认从配置读取
    """
    # 使用默认值
    bm25_collection = bm25_collection or DEFAULT_COLLECTION
    persist_directory = persist_directory or DEFAULT_PERSIST_DIR
    k1 = k1 if k1 is not None else DEFAULT_K1
    b = b if b is not None else DEFAULT_B
    delta = delta if delta is not None else DEFAULT_DELTA
    method = method or DEFAULT_METHOD
    print("=" * 60)
    print("开始初始化 BM25Store")
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
    
    # 3. 初始化 BM25Store
    print(f"\n3. 初始化 BM25Store")
    print(f"   集合名称: {bm25_collection}")
    print(f"   持久化目录: {persist_directory}")
    print(f"   BM25 参数: k1={k1}, b={b}, delta={delta}, method={method}")
    try:
        store = BM25Store(
            collection_name=bm25_collection,
            persist_directory=persist_directory,
            k1=k1,
            b=b,
            delta=delta,
            method=method
        )
        print(f"   ✅ BM25Store 初始化成功")
    except Exception as e:
        print(f"   ❌ BM25Store 初始化失败: {e}")
        return False
    
    # 4. 导入数据
    print(f"\n4. 导入数据到 BM25Store")
    print(f"   正在处理...")
    
    batch_size = 500
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
        # 同时添加拼音和代码，提高搜索命中率
        content = f"{name} {symbol}"
        
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
    
    # 保存索引
    print(f"\n   正在保存 BM25 索引...")
    try:
        store.save()
        print(f"   ✅ 索引保存成功")
    except Exception as e:
        print(f"   ⚠️ 索引保存失败: {e}")
    
    print(f"\n   ✅ 导入完成")
    print(f"   成功: {inserted_count}")
    print(f"   跳过: {skipped_count}")
    
    # 5. 验证
    print(f"\n5. 验证导入结果")
    final_count = store.count()
    print(f"   BM25Store 文档总数: {final_count}")
    
    # 6. 测试查询
    print(f"\n6. 测试 BM25 关键词查询")
    try:
        # 测试用例1: 按名称查询
        test_query = "平安银行"
        results = store.search(test_query, top_k=3)
        print(f"\n   查询: '{test_query}'")
        for i, r in enumerate(results, 1):
            print(f"   {i}. [rank={r.rank}, score={r.score:.3f}] {r.content}")
        
        # 测试用例2: 按代码查询
        test_query = "000001"
        results = store.search(test_query, top_k=3)
        print(f"\n   查询: '{test_query}'")
        for i, r in enumerate(results, 1):
            print(f"   {i}. [rank={r.rank}, score={r.score:.3f}] {r.content}")
        
        # 测试用例3: 关键词搜索
        test_query = "银行"
        results = store.search(test_query, top_k=5)
        print(f"\n   查询: '{test_query}' (前5条)")
        for i, r in enumerate(results, 1):
            print(f"   {i}. [rank={r.rank}, score={r.score:.3f}] {r.content}")
            
    except Exception as e:
        print(f"   ⚠️ 查询测试失败: {e}")
    
    # 关闭连接
    client.close()
    
    print("\n" + "=" * 60)
    print("初始化完成！")
    print("=" * 60)
    
    return True


def clear_bm25_store(collection_name=None, persist_directory=None):
    """
    清空 BM25Store 中的股票数据
    
    Usage:
        python scripts/init_bm25_store.py --clear
    """
    collection_name = collection_name or DEFAULT_COLLECTION
    persist_directory = persist_directory or DEFAULT_PERSIST_DIR
    
    print(f"清空 BM25Store 集合: {collection_name}")
    try:
        store = BM25Store(
            collection_name=collection_name,
            persist_directory=persist_directory
        )
        store.clear()
        print("✅ 清空完成")
        return True
    except Exception as e:
        print(f"❌ 清空失败: {e}")
        return False


def rebuild_bm25_index(collection_name=None, persist_directory=None):
    """
    重建 BM25 索引（不重新导入数据）
    
    Usage:
        python scripts/init_bm25_store.py --rebuild-index
    """
    collection_name = collection_name or DEFAULT_COLLECTION
    persist_directory = persist_directory or DEFAULT_PERSIST_DIR
    
    print(f"重建 BM25 索引: {collection_name}")
    try:
        store = BM25Store(
            collection_name=collection_name,
            persist_directory=persist_directory
        )
        # 强制重建索引
        store._build_index()
        store.save()
        print(f"✅ 索引重建完成，共 {store.count()} 个文档")
        return True
    except Exception as e:
        print(f"❌ 索引重建失败: {e}")
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="初始化 BM25Store 股票数据")
    parser.add_argument(
        "--clear",
        action="store_true",
        help="清空 BM25Store 数据"
    )
    parser.add_argument(
        "--rebuild-index",
        action="store_true",
        help="重建 BM25 索引（不重新导入数据）"
    )
    parser.add_argument(
        "--mongo-uri",
        default="mongodb://localhost:27017",
        help="MongoDB URI (默认: mongodb://localhost:27017)"
    )
    parser.add_argument(
        "--collection",
        default=DEFAULT_COLLECTION,
        help=f"BM25Store 集合名称 (默认: {DEFAULT_COLLECTION})"
    )
    parser.add_argument(
        "--persist-dir",
        default=DEFAULT_PERSIST_DIR,
        help=f"BM25 数据持久化目录 (默认: {DEFAULT_PERSIST_DIR})"
    )
    parser.add_argument(
        "--k1",
        type=float,
        default=DEFAULT_K1,
        help=f"BM25 k1 参数 (默认: {DEFAULT_K1})"
    )
    parser.add_argument(
        "--b",
        type=float,
        default=DEFAULT_B,
        help=f"BM25 b 参数 (默认: {DEFAULT_B})"
    )
    parser.add_argument(
        "--delta",
        type=float,
        default=DEFAULT_DELTA,
        help=f"BM25+ delta 参数 (默认: {DEFAULT_DELTA})"
    )
    parser.add_argument(
        "--method",
        default=DEFAULT_METHOD,
        help=f"BM25 计算方法 (默认: {DEFAULT_METHOD})"
    )
    
    args = parser.parse_args()
    
    if args.clear:
        clear_bm25_store(args.collection, args.persist_dir)
    elif args.rebuild_index:
        rebuild_bm25_index(args.collection, args.persist_dir)
    else:
        init_stock_bm25_store(
            mongo_uri=args.mongo_uri,
            bm25_collection=args.collection,
            persist_directory=args.persist_dir,
            k1=args.k1,
            b=args.b,
            delta=args.delta,
            method=args.method
        )
