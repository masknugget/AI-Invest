import json
import os
from datetime import datetime
from typing import List

from bson import json_util
from pymongo import MongoClient

# 连接配置
MONGO_URI = "mongodb://localhost:27017/tradingagentscn"
DB_NAME = "tradingagentscn"
INPUT_DIR = r"F:\project_work\hf\AI-Invest\mock\mg_p_risk"

# p_advisor.py 中涉及的所有集合名称
COLLECTIONS: List[str] = [
    "qa_pair",
    "market_fundamental_analysis_v1",
    "p_advisor_dimensions",
    "user_industry_distribution",
    "p_advisor_risk_alerts",
    "p_advisor_risk_report",
    "p_advisor_result",
    "p_advisor_faq",
    "p_advisor_rebalance_plans",
    "p_advisor_stress_report",
]


def import_collection(client: MongoClient, coll_name: str, input_dir: str) -> int:
    """从 JSONL 文件导入单个集合，返回导入的文档数。"""
    input_path = os.path.join(input_dir, f"{coll_name}.jsonl")
    if not os.path.exists(input_path):
        print(f"   ⚠️ 文件不存在，跳过: {input_path}")
        return 0

    db = client[DB_NAME]
    coll = db[coll_name]

    count = 0
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            doc = json_util.loads(line)
            # 确保没有遗留的 _id，让 MongoDB 自动生成
            doc.pop("_id", None)
            coll.insert_one(doc)
            count += 1

    return count


def main() -> None:
    print("=" * 60)
    print("开始从本地 mock 目录导入 p_advisor 相关集合到 MongoDB")
    print(f"输入目录: {INPUT_DIR}")
    print("=" * 60)

    if not os.path.isdir(INPUT_DIR):
        print(f"❌ 输入目录不存在: {INPUT_DIR}")
        return

    print(f"\n🔗 正在连接 MongoDB: {MONGO_URI}")
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        print("✅ MongoDB 连接成功")
    except Exception as e:
        print(f"❌ MongoDB 连接失败: {e}")
        return

    total_docs = 0
    for coll_name in COLLECTIONS:
        print(f"\n📦 正在导入集合: {coll_name}")
        try:
            count = import_collection(client, coll_name, INPUT_DIR)
            print(f"   ✅ 已导入 {count} 条记录到 {coll_name}")
            total_docs += count
        except Exception as e:
            print(f"   ❌ 导入失败: {e}")

    print("\n" + "=" * 60)
    print(f"🎉 导入完成，总计 {total_docs} 条记录")
    print(f"📁 输入目录: {INPUT_DIR}")
    print(f"⏰ 完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)


if __name__ == "__main__":
    main()
