import json
import os
from datetime import datetime
from typing import List

from bson import json_util
from pymongo import MongoClient

# 连接配置
MONGO_URI = "mongodb://localhost:27017/tradingagentscn"
DB_NAME = "tradingagentscn"
OUTPUT_DIR = r"F:\project_work\hf\AI-Invest\mock\mg_p_risk"

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


def export_collection(client: MongoClient, coll_name: str, output_dir: str) -> int:
    """导出单个集合到 JSONL 文件，返回导出的文档数。"""
    db = client[DB_NAME]
    coll = db[coll_name]
    output_path = os.path.join(output_dir, f"{coll_name}.jsonl")

    count = 0
    with open(output_path, "w", encoding="utf-8") as f:
        for doc in coll.find({}):
            # 移除 MongoDB 的 _id，重新导入时自动生成新 _id，避免冲突
            doc.pop("_id", None)
            line = json_util.dumps(doc, ensure_ascii=False)
            f.write(line + "\n")
            count += 1

    return count


def main() -> None:
    print("=" * 60)
    print("开始导出 p_advisor 相关 MongoDB 集合到本地 mock 目录")
    print(f"输出目录: {OUTPUT_DIR}")
    print("=" * 60)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"\n✅ 输出目录已就绪: {OUTPUT_DIR}")

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
        print(f"\n📦 正在导出集合: {coll_name}")
        try:
            count = export_collection(client, coll_name, OUTPUT_DIR)
            print(f"   ✅ 已导出 {count} 条记录 -> {coll_name}.jsonl")
            total_docs += count
        except Exception as e:
            print(f"   ❌ 导出失败: {e}")

    print("\n" + "=" * 60)
    print(f"🎉 导出完成，总计 {total_docs} 条记录")
    print(f"📁 输出目录: {OUTPUT_DIR}")
    print(f"⏰ 完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)


if __name__ == "__main__":
    main()
