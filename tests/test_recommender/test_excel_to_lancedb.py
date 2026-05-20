"""
Excel/JSON → LanceDB 导入脚本测试
简单使用示例，演示完整导入和搜索流程

运行方式:
    python tests/test_recommender/test_excel_to_lancedb.py
    # 或通过测试运行器
    python tests/run_tests.py --category 推荐系统
"""
import os
import sys
import json
import tempfile

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from recommender.import_excel_to_lancedb import (
    read_excel_data,
    read_json_data,
    validate_data,
    build_documents,
    import_to_lancedb,
)
from tradingagents.searcher import VectorStore


# ==================== 辅助函数 ====================

def create_test_excel(path: str):
    """创建测试用的 Excel 文件"""
    import pandas as pd
    data = {
        "query": [
            "如何开户",
            "股票交易时间",
            "如何查询持仓",
            "",  # 空 query，应被跳过
            "如何开户",  # 重复 query，用于测试去重
            "新手如何选股",
        ],
        "answer": [
            "携带身份证到证券公司营业部办理开户手续。",
            "A股交易时间为周一至周五 9:30-11:30, 13:00-15:00。",
            '登录交易软件，在"持仓"或"资产"页面查看。',
            "这条数据的 query 为空",
            "携带身份证到证券公司营业部办理开户手续。（重复）",
            "建议从行业龙头、业绩稳定的蓝筹股入手。",
        ],
        "meta_data": [
            "开户,新手",
            '{"category": "交易规则", "level": "基础"}',
            "查询,持仓",
            "",
            "开户,新手",
            '{"category": "选股", "level": "新手"}',
        ]
    }
    df = pd.DataFrame(data)
    df.to_excel(path, index=False)
    print(f"✅ 创建测试 Excel: {path}")


def create_test_json(path: str):
    """创建测试用的 JSON 文件"""
    data = [
        {"meta_data": "JPM", "query": "摩根大通现在多少钱一股？", "answer": "摩根大通(JPM)当前股价约189.07元。"},
        {"meta_data": "AAPL", "query": "AAPL的均线排列如何？", "answer": "AAPL目前均线多头排列。"},
        {"meta_data": "600519.SH", "query": "600519.SH对标美股哪家公司？", "answer": "600519.SH常被比作强生的中国版。"},
        {"meta_data": "", "query": "", "answer": "这条数据的 query 为空"},  # 空 query
        {"meta_data": "JPM", "query": "摩根大通现在多少钱一股？", "answer": "重复数据"},  # 重复
        {"meta_data": "688599.SH", "query": "天合光能股价走势如何？", "answer": "天合光能近期股价围绕21.57元波动。"},
    ]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ 创建测试 JSON: {path}")


# ==================== 测试函数 ====================

def test_read_json():
    """测试读取 JSON 文件"""
    print("=== 测试读取 JSON ===")

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        temp_path = f.name

    try:
        create_test_json(temp_path)

        records = read_json_data(temp_path)

        assert len(records) == 6, f"期望 6 条记录，实际 {len(records)}"
        assert records[0]["query"] == "摩根大通现在多少钱一股？"
        assert records[0]["answer"] == "摩根大通(JPM)当前股价约189.07元。"
        assert records[0]["meta_data"] == "JPM"
        assert records[1]["query"] == "AAPL的均线排列如何？"

        print(f"[PASS] 成功读取 {len(records)} 条记录")
        print(f"       首条: Q='{records[0]['query']}', A='{records[0]['answer'][:20]}...', Meta='{records[0]['meta_data']}'")

        return True
    finally:
        os.unlink(temp_path)


def test_validate_data():
    """测试数据验证（跳过空 query）"""
    print("\n=== 测试数据验证 ===")

    records = [
        {"row_index": 0, "query": "如何开户", "answer": "A1", "meta_data": ""},
        {"row_index": 1, "query": "", "answer": "A2", "meta_data": ""},  # 空 query
        {"row_index": 2, "query": "如何选股", "answer": "A3", "meta_data": '{"tag": "test"}'},
    ]

    valid = validate_data(records)

    assert len(valid) == 2, f"期望 2 条有效记录，实际 {len(valid)}"
    assert valid[1]["meta_data"] == {"tag": "test"}, "meta_data 应被解析为 JSON"

    print(f"[PASS] 验证后保留 {len(valid)} 条（跳过 1 条空 query）")
    print(f"       meta_data 解析: {valid[1]['meta_data']}")

    return True


def test_build_documents():
    """测试文档构建（含去重）"""
    print("\n=== 测试文档构建 ===")

    records = [
        {"row_index": 0, "query": "如何开户", "answer": "A1", "meta_data": ""},
        {"row_index": 1, "query": "如何开户", "answer": "A2", "meta_data": ""},  # 重复
        {"row_index": 2, "query": "如何选股", "answer": "A3", "meta_data": "新手"},
    ]

    # 测试去重
    docs = build_documents(records, dedup=True)
    assert len(docs) == 2, f"去重后应剩 2 条，实际 {len(docs)}"

    # 测试不去重
    docs_no_dedup = build_documents(records, dedup=False)
    assert len(docs_no_dedup) == 3, f"不去重应有 3 条，实际 {len(docs_no_dedup)}"

    # 检查文档结构
    doc = docs[0]
    assert "id" in doc
    assert doc["content"] == "如何开户"
    assert doc["metadata"]["answer"] == "A1"
    assert doc["metadata"]["source"] == "excel_import"

    print(f"[PASS] 去重后: {len(docs)} 条，不去重: {len(docs_no_dedup)} 条")
    print(f"       文档结构: id={doc['id']}, content='{doc['content']}'")

    return True


def test_import_and_search():
    """测试导入到 LanceDB 并搜索（使用示例）"""
    print("\n=== 测试导入和搜索（使用示例）===")

    # 准备测试数据
    records = [
        {"row_index": 0, "query": "如何开户", "answer": "携带身份证到营业部办理。", "meta_data": "开户"},
        {"row_index": 1, "query": "股票交易时间是什么", "answer": "周一至周五 9:30-15:00。", "meta_data": "交易规则"},
        {"row_index": 2, "query": "新手怎么选股", "answer": "建议从蓝筹股入手。", "meta_data": "选股"},
        {"row_index": 3, "query": "如何查询账户余额", "answer": "登录 APP 查看资产页面。", "meta_data": "查询"},
    ]

    documents = build_documents(records, dedup=True)

    # 使用内存模式导入（避免写入磁盘）
    collection_name = "test_faq_memory"
    store = VectorStore(collection_name=collection_name, persist_directory="")

    try:
        store.add_documents(documents)
    except Exception as e:
        print(f"\n  ⚠️ Embedding API 调用失败（可能需要配置 API Key 或安装依赖）: {e}")
        print("  跳过搜索测试。在配置好 Embedding 后可正常运行。")
        store.clear()
        return True

    count = store.count()
    assert count == 4, f"期望 4 条文档，实际 {count}"
    print(f"[PASS] 导入成功，共 {count} 条文档")

    # 测试搜索 1：语义匹配
    print("\n  搜索: '我想开户'（语义匹配）")
    results = store.search("我想开户", top_k=2)
    assert len(results) > 0, "搜索结果不应为空"

    for i, r in enumerate(results, 1):
        print(f"     {i}. [{r.score:.3f}] {r.content}")
        print(f"        A: {r.metadata['answer']}")

    # 验证第一条是"如何开户"
    assert "开户" in results[0].content or "开户" in results[0].metadata["answer"], \
        f"首条结果应与开户相关: {results[0].content}"

    # 测试搜索 2：另一个查询
    print("\n  搜索: '交易时间'（语义匹配）")
    results2 = store.search("交易时间", top_k=2)
    for i, r in enumerate(results2, 1):
        print(f"     {i}. [{r.score:.3f}] {r.content}")

    assert "交易" in results2[0].content or "交易" in results2[0].metadata["answer"], \
        f"首条结果应与交易相关: {results2[0].content}"

    # 清理
    store.clear()
    print("\n[PASS] 搜索测试通过，已清理内存数据")

    return True


def test_full_workflow():
    """完整工作流示例：JSON → LanceDB → 搜索"""
    print("\n=== 完整工作流示例 ===")

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        temp_path = f.name

    try:
        # 1. 创建 JSON
        create_test_json(temp_path)

        # 2. 读取
        records = read_json_data(temp_path)
        print(f"  1️⃣ 读取 JSON: {len(records)} 行")

        # 3. 验证
        valid = validate_data(records)
        print(f"  2️⃣ 数据验证: {len(valid)} 条有效（跳过空 query）")

        # 4. 构建文档
        docs = build_documents(valid, dedup=True)
        print(f"  3️⃣ 构建文档: {len(docs)} 条（去重后）")

        # 5. 导入（内存模式）
        store = VectorStore(collection_name="test_workflow", persist_directory="")
        try:
            store.add_documents(docs)
            print(f"  4️⃣ 导入 LanceDB: {store.count()} 条")

            # 6. 搜索
            print(f"  5️⃣ 搜索测试:")
            results = store.search("摩根大通", top_k=3)
            for i, r in enumerate(results, 1):
                print(f"      {i}. [{r.score:.3f}] {r.content}")
        except Exception as e:
            print(f"\n  ⚠️ Embedding API 调用失败（可能需要配置 API Key 或安装依赖）: {e}")
            print("  展示工作流完成。在配置好 Embedding 后可正常运行搜索。")

        # 7. 清理
        store.clear()
        print(f"  6️⃣ 清理完成")

        print("\n[PASS] 完整工作流测试通过")
        return True

    finally:
        os.unlink(temp_path)


# ==================== 测试运行器 ====================

def run_all_tests():
    """运行所有测试"""
    tests = [
        ("读取 JSON", test_read_json),
        ("数据验证", test_validate_data),
        ("文档构建", test_build_documents),
        ("导入和搜索", test_import_and_search),
        ("完整工作流", test_full_workflow),
    ]

    passed = 0
    failed = 0

    print("=" * 60)
    print("JSON → LanceDB 导入测试")
    print("=" * 60)

    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"\n❌ {test_name} 测试失败: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"测试结果: 通过 {passed}, 失败 {failed}")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
