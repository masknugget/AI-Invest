"""
VectorStore 使用示例 - insight_news 集合

展示如何使用 LanceDB 中的 insight_news 数据进行向量搜索。
"""

import os
import sys

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from tradingagents.searcher.vector_store import VectorStore


def example_basic_search():
    """示例1: 基础相似性搜索"""
    print("=== 示例1: 基础相似性搜索 ===")

    store = VectorStore(collection_name="insight_news")

    # 搜索与"股市上涨"相关的新闻
    results = store.search("股市上涨", top_k=5)

    print(f"查询: '股市上涨', 返回 {len(results)} 条结果\n")
    for i, r in enumerate(results, 1):
        print(f"{i}. [相似度: {r.score:.3f}] {r.content[:80]}...")
        print(f"   元数据: {r.metadata}\n")


def example_filtered_search():
    """示例2: 带元数据过滤的搜索"""
    print("\n=== 示例2: 带元数据过滤的搜索 ===")

    store = VectorStore(collection_name="insight_news")

    # 搜索特定来源的新闻
    results = store.search(
        "财报",
        top_k=5,
        filter_metadata={"source": "财经新闻"}
    )

    print(f"查询: '财报' (过滤 source='财经新闻'), 返回 {len(results)} 条结果\n")
    for i, r in enumerate(results, 1):
        print(f"{i}. [相似度: {r.score:.3f}] {r.content[:80]}...")


def example_get_by_id():
    """示例3: 根据 ID 获取文档"""
    print("\n=== 示例3: 根据 ID 获取文档 ===")

    store = VectorStore(collection_name="insight_news")

    # 先列出所有文档，获取第一个 ID
    docs = store.list_all(limit=1)
    if not docs:
        print("集合中没有文档")
        return

    doc_id = docs[0].id
    print(f"获取文档 ID: {doc_id}")

    result = store.get(doc_id)
    if result:
        print(f"内容: {result.content[:100]}...")
        print(f"元数据: {result.metadata}")
    else:
        print("文档不存在")


def example_count_and_list():
    """示例4: 统计和列表演示"""
    print("\n=== 示例4: 统计和列表演示 ===")

    store = VectorStore(collection_name="insight_news")

    # 获取总数
    total = store.count()
    print(f"insight_news 集合文档总数: {total}")

    # 列出前 3 条
    docs = store.list_all(limit=3)
    print(f"\n前 {len(docs)} 条文档:")
    for i, doc in enumerate(docs, 1):
        print(f"{i}. ID: {doc.id}")
        print(f"   内容: {doc.content[:60]}...")


def example_multi_query_search():
    """示例5: 多查询对比搜索"""
    print("\n=== 示例5: 多查询对比搜索 ===")

    store = VectorStore(collection_name="insight_news")

    queries = ["人工智能", "新能源汽车", "宏观经济"]

    for query in queries:
        print(f"\n查询: '{query}'")
        results = store.search(query, top_k=3)
        for i, r in enumerate(results, 1):
            print(f"  {i}. [{r.score:.3f}] {r.content[:60]}...")


if __name__ == "__main__":
    print("VectorStore insight_news 使用示例\n")
    print("=" * 50)

    try:
        example_basic_search()
        example_filtered_search()
        example_get_by_id()
        example_count_and_list()
        example_multi_query_search()

        print("\n" + "=" * 50)
        print("所有示例执行完成")

    except Exception as e:
        print(f"示例执行失败: {e}")
        import traceback
        traceback.print_exc()
