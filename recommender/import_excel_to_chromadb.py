"""
Excel → ChromaDB 导入脚本
用于将 xlsx 格式的问答数据导入向量数据库，支持语义搜索

Usage:
    python recommender/import_excel_to_chromadb.py --input data/faq.xlsx
    python recommender/import_excel_to_chromadb.py --input data/faq.xlsx --collection faq_v1 --clear
    python recommender/import_excel_to_chromadb.py --input data/faq.xlsx --dry-run
    python recommender/import_excel_to_chromadb.py --input data/faq.xlsx --test-query "如何开户"
"""

import os
import sys
import json
import hashlib
from typing import List, Dict, Any, Optional, Union

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import pandas as pd
from tradingagents.searcher import VectorStore, create_vector_store


# ==================== 固定配置 ====================

INPUT_FILE = r"F:\project_work\hf\AI-Invest\scripts\data_local\data_qa_5000.json"
COLLECTION_NAME = "stock_qa"
BATCH_SIZE = 50
CLEAR_FIRST = False      # 导入前是否清空集合
ENABLE_DEDUP = True      # 是否基于 query 去重
TEST_QUERY = "摩根大通股价"  # 导入后测试查询，设为空字符串则不测试


# ==================== 配置常量 ====================

DEFAULT_COLLECTION = "faq"
DEFAULT_BATCH_SIZE = 50
REQUIRED_COLUMNS = ["query", "answer"]
OPTIONAL_COLUMNS = ["meta_data"]


# ==================== Excel 读取 ====================

def read_excel_data(
    file_path: str,
    sheet_name: Optional[Union[str, int]] = 0,
    header: int = 0
) -> List[Dict[str, Any]]:
    """
    读取 Excel 文件，返回标准化记录列表
    
    Args:
        file_path: xlsx 文件路径
        sheet_name: 工作表名称，默认第一个
        header: 表头行号，默认第 0 行
        
    Returns:
        List[Dict]: 每条记录包含 query, answer, meta_data(可选)
    """
    print(f"📖 读取 Excel: {file_path}")
    
    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name, header=header)
    except Exception as e:
        print(f"❌ 读取 Excel 失败: {e}")
        sys.exit(1)
    
    # 标准化列名（去除空格，转小写）
    original_columns = list(df.columns)
    df.columns = [str(c).strip().lower() for c in df.columns]
    
    print(f"   原始列名: {original_columns}")
    print(f"   数据行数: {len(df)}")
    
    # 检查必填列
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        print(f"❌ 缺少必填列: {missing}")
        print(f"   可用列: {list(df.columns)}")
        sys.exit(1)
    
    # 转换为字典列表
    records = []
    for idx, row in df.iterrows():
        record = {
            "row_index": int(idx),
            "query": str(row.get("query", "")).strip(),
            "answer": str(row.get("answer", "")).strip(),
            "meta_data": str(row.get("meta_data", "")).strip() if "meta_data" in df.columns else "",
        }
        records.append(record)
    
    return records


# ==================== JSON 读取 ====================

def read_json_data(file_path: str) -> List[Dict[str, Any]]:
    """
    读取 JSON 文件，返回标准化记录列表
    
    期望格式:
        [
            {"meta_data": "AAPL", "query": "苹果股价多少？", "answer": "约189元。"},
            ...
        ]
    
    Args:
        file_path: json 文件路径
        
    Returns:
        List[Dict]: 每条记录包含 query, answer, meta_data(可选)
    """
    print(f"📖 读取 JSON: {file_path}")
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ 读取 JSON 失败: {e}")
        sys.exit(1)
    
    if not isinstance(data, list):
        print(f"❌ JSON 根元素应为数组，实际为: {type(data).__name__}")
        sys.exit(1)
    
    print(f"   数据条数: {len(data)}")
    
    # 检查第一条记录结构
    if data and not isinstance(data[0], dict):
        print(f"❌ JSON 数组元素应为对象，实际为: {type(data[0]).__name__}")
        sys.exit(1)
    
    # 检查必填字段
    if data:
        first_keys = set(str(k).lower() for k in data[0].keys())
        missing = [col for col in REQUIRED_COLUMNS if col not in first_keys]
        if missing:
            print(f"❌ 缺少必填字段: {missing}")
            print(f"   可用字段: {list(data[0].keys())}")
            sys.exit(1)
    
    # 转换为标准化记录
    records = []
    for idx, item in enumerate(data):
        # 处理字段名大小写（支持 meta_data / metaData / meta 等）
        item_lower = {str(k).lower(): v for k, v in item.items()}

        # 将 uuid 和 meta_data 组合为新的 dict 格式
        uuid_val = str(item_lower.get("uuid", "")).strip()
        name_val = str(item_lower.get("meta_data", "")).strip()

        meta_dict = {}
        if uuid_val:
            meta_dict["uuid"] = uuid_val
        if name_val:
            meta_dict["name"] = name_val

        record = {
            "row_index": idx,
            "query": str(item_lower.get("query", "")).strip(),
            "answer": str(item_lower.get("answer", "")).strip(),
            "meta_data": meta_dict,
        }
        records.append(record)

    return records


# ==================== 数据验证 ====================

def validate_data(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    验证并清洗数据
    
    - 跳过 query 为空的记录
    - 尝试解析 meta_data 为 JSON，失败则保留原字符串
    
    Returns:
        List[Dict]: 清洗后的记录
    """
    print("\n🔍 数据验证...")
    
    valid_records = []
    skipped = 0
    
    for record in records:
        if not record["query"]:
            skipped += 1
            continue
        
        # 尝试解析 meta_data 为 JSON（仅当它是字符串时）
        meta_raw = record["meta_data"]
        if isinstance(meta_raw, str) and meta_raw:
            try:
                record["meta_data"] = json.loads(meta_raw)
            except json.JSONDecodeError:
                # 不是 JSON，保留原字符串
                pass
        
        valid_records.append(record)
    
    print(f"   ✅ 有效记录: {len(valid_records)}")
    if skipped:
        print(f"   ⚠️  跳过空 query: {skipped}")
    
    return valid_records


# ==================== ID 生成 ====================

def generate_doc_id(record: Dict[str, Any], index: int, use_hash: bool = False) -> str:
    """
    生成文档 ID
    
    Args:
        record: 数据记录
        index: 行号索引
        use_hash: 是否基于 query 内容生成 MD5（用于去重）
        
    Returns:
        str: 文档 ID
    """
    if use_hash and record["query"]:
        # 基于 query 内容生成 MD5，确保相同 query 的 ID 一致
        md5_hash = hashlib.md5(record["query"].encode("utf-8")).hexdigest()[:12]
        return f"faq_{md5_hash}"
    else:
        return f"faq_{index}"


# ==================== ChromaDB 导入 ====================

def build_documents(
    records: List[Dict[str, Any]],
    dedup: bool = True
) -> List[Dict[str, Any]]:
    """
    将记录转换为 VectorStore 可用的文档格式
    
    Args:
        records: 清洗后的记录
        dedup: 是否基于 query 去重
        
    Returns:
        List[Dict]: 文档列表，每项包含 id, content, metadata
    """
    print("\n📦 构建文档...")
    
    documents = []
    seen_ids = set()
    
    for i, record in enumerate(records):
        doc_id = generate_doc_id(record, i, use_hash=dedup)
        
        if dedup and doc_id in seen_ids:
            continue
        seen_ids.add(doc_id)
        
        # 构建 metadata
        metadata = {
            "answer": record["answer"],
            "source": "excel_import",
            "row_index": record["row_index"],
        }
        
        # 添加 meta_data（ChromaDB 只支持 str/int/float/bool/None）
        meta_value = record["meta_data"]
        if isinstance(meta_value, dict):
            metadata["meta_data"] = json.dumps(meta_value, ensure_ascii=False)
        elif meta_value:
            metadata["meta_data"] = meta_value
        
        doc = {
            "id": doc_id,
            "content": record["query"],  # query 用于 embedding 和搜索
            "metadata": metadata,
        }
        documents.append(doc)
    
    if dedup:
        dup_count = len(records) - len(documents)
        if dup_count > 0:
            print(f"   🔄 去重后: {len(documents)} (移除重复: {dup_count})")
    
    print(f"   ✅ 文档总数: {len(documents)}")
    return documents


def import_to_chromadb(
    documents: List[Dict[str, Any]],
    collection_name: str = DEFAULT_COLLECTION,
    batch_size: int = DEFAULT_BATCH_SIZE,
    clear_first: bool = False,
) -> bool:
    """
    导入文档到 ChromaDB
    
    Args:
        documents: 文档列表
        collection_name: 集合名称
        batch_size: 批量大小
        clear_first: 导入前是否清空集合
        
    Returns:
        bool: 是否成功
    """
    print(f"\n🚀 开始导入到 ChromaDB")
    print(f"   集合: {collection_name}")
    print(f"   批量大小: {batch_size}")
    
    try:
        store = VectorStore(collection_name=collection_name)
    except Exception as e:
        print(f"❌ 初始化 VectorStore 失败: {e}")
        return False
    
    # 清空（如需要）
    if clear_first:
        print("   🗑️  清空现有集合...")
        store.clear()
    
    # 批量导入
    total = len(documents)
    inserted = 0
    failed = 0
    
    for i in range(0, total, batch_size):
        batch = documents[i:i + batch_size]
        try:
            store.add_documents(batch)
            inserted += len(batch)
            print(f"   已导入: {inserted}/{total}", end="\r")
        except Exception as e:
            print(f"\n   ❌ 批量导入失败 (第 {i} 批): {e}")
            failed += len(batch)
    
    print()  # 换行
    print(f"   ✅ 导入完成: 成功 {inserted}, 失败 {failed}")
    print(f"   📊 集合文档总数: {store.count()}")
    
    return failed == 0


# ==================== 测试查询 ====================

def test_search(collection_name: str, query: str, top_k: int = 3):
    """
    测试搜索
    
    Args:
        collection_name: 集合名称
        query: 测试查询文本
        top_k: 返回结果数量
    """
    print(f"\n🔍 测试查询: '{query}'")
    
    try:
        store = VectorStore(collection_name=collection_name)
        results = store.search(query, top_k=top_k)
        
        if not results:
            print("   ⚠️  无结果")
            return
        
        print(f"   返回 {len(results)} 条结果:\n")
        for i, r in enumerate(results, 1):
            print(f"   {i}. [相似度: {r.score:.3f}]")
            print(f"      Q: {r.content}")
            answer = r.metadata.get("answer", "")
            # 截断长答案
            display_answer = answer[:100] + "..." if len(answer) > 100 else answer
            print(f"      A: {display_answer}")
            if r.metadata.get("meta_data"):
                print(f"      Meta: {r.metadata['meta_data']}")
            print()
            
    except Exception as e:
        print(f"   ❌ 查询失败: {e}")


# ==================== 主入口 ====================

def main():
    """固定配置入口：直接修改上方 INPUT_FILE 等常量即可"""
    INPUT_FILE = r'F:\project_work\hf\AI-Invest\scripts\data_local\data_qa_5000.json'
    print("=" * 60)
    print("JSON → ChromaDB 导入工具")
    print("=" * 60)
    print(f"输入文件: {INPUT_FILE}")
    print(f"目标集合: {COLLECTION_NAME}")
    print(f"去重: {'开启' if ENABLE_DEDUP else '关闭'}")
    print(f"清空: {'是' if CLEAR_FIRST else '否'}")
    print("=" * 60)
    
    # 1. 读取 JSON
    records = read_json_data(INPUT_FILE)
    
    # 2. 验证数据
    valid_records = validate_data(records)
    
    if not valid_records:
        print("\n❌ 没有有效数据可导入")
        sys.exit(1)
    
    # 3. 构建文档
    documents = build_documents(valid_records, dedup=ENABLE_DEDUP)
    
    # 4. 导入到 ChromaDB
    success = import_to_chromadb(
        documents=documents,
        collection_name=COLLECTION_NAME,
        batch_size=BATCH_SIZE,
        clear_first=CLEAR_FIRST,
    )
    
    if not success:
        print("\n❌ 导入未完全成功")
        sys.exit(1)
    
    # 5. 测试查询
    if TEST_QUERY:
        test_search(COLLECTION_NAME, TEST_QUERY, top_k=3)
    
    print("\n🎉 全部完成！")


if __name__ == "__main__":
    main()
