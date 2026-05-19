import os
import json
import random
import sys
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

from recommender.newsReader.llms import chat_once
from recommender.newsReader.utils import parse_json_from_llm

from scripts.data_handler.news.prompt_userprofiles import build_user_profile_prompt
from app.core.database import get_mongo_db_sync

path_dir = r'F:\work\report'


def load_dict(filename):
    """从 JSON 文件读取 dict"""
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)


def load_data():
    """加载所有 JSON 数据到 data_out"""
    data_out = []
    for filename in os.listdir(path_dir):
        if str(filename).endswith(".json"):
            filepath = os.path.join(path_dir, filename)
            data = load_dict(filepath)
            data_out.append(data)
    return data_out


def sample_records(data_out: List[Dict[str, Any]], n: int = 10) -> List[Dict[str, Any]]:
    """从 data_out 中随机抽取 n 条记录"""
    if len(data_out) <= n:
        return data_out
    return random.sample(data_out, n)


def build_news_browsing_data(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """将抽取的记录转换为 recent_news_browsing_7d 格式"""
    browsing = []
    now = datetime.now(timezone.utc)

    for i, record in enumerate(records):
        content = record.get("content", "")
        title = record.get("title", content[:80] + "..." if len(content) > 80 else content)
        summary = content[:200] + "..." if len(content) > 200 else content

        # 模拟递减的时间戳（最近 7 天内）
        ts = (now - timedelta(hours=i * 6)).strftime("%Y-%m-%dT%H:%M:%SZ")

        browsing.append({
            "title": title,
            "summary": summary,
            "category": record.get("category", "General"),
            "dwellSec": random.randint(30, 300),
            "timestamp": ts,
        })

    return browsing


def main():
    """主函数：加载数据、随机抽取、利用 build_user_profile_prompt 构建 prompt"""
    print("=" * 60)
    print("用户画像 Prompt 生成器")
    print("=" * 60)

    # 1. 加载数据
    print("\n[1/4] 加载数据...")
    data_out = load_data()
    print(f"      共加载 {len(data_out)} 条记录")

    # 2. 随机抽取 10 条
    print("\n[2/4] 随机抽取 10 条记录...")
    sampled = sample_records(data_out, n=10)
    print(f"      成功抽取 {len(sampled)} 条")

    # 3. 构造 recent_news_browsing_7d
    print("\n[3/4] 构造浏览历史数据...")
    recent_news_browsing_7d = build_news_browsing_data(sampled)
    for i, news in enumerate(recent_news_browsing_7d, 1):
        print(f"      [{i}] {news['title'][:50]}... (停留 {news['dwellSec']}s)")

    # 4. 构造 user_data 并调用 build_user_profile_prompt
    print("\n[4/4] 调用 build_user_profile_prompt 生成 prompt...")

    user_data = {
        "recent_news_browsing_7d": recent_news_browsing_7d,
        "clickstream_7d": [],
        "search_logs_30d": [],
        "trade_history_30d": [],
        "watchlist_snapshot": [],
        "content_engagement_14d": [],
    }

    result = build_user_profile_prompt(
        user_data=user_data,
        market_context="中东地缘冲突持续，美联储维持利率不变预期升温。",
        include_few_shot=True,
    )

    # 5. 输出结果
    print("\n" + "=" * 60)
    print("生成的 Prompt (SYSTEM 前 500 字)")
    print("=" * 60)
    print(result["system"][:500] + "...")
    print("\n--- USER (前 500 字) ---\n")
    print(result["user"][:500] + "...")
    print("\n--- META ---")
    print(result["meta"])

    out_json = chat_once(result['system'] + result['user'])
    out_json = parse_json_from_llm(out_json)
    out_json['user_id'] = 'admin123'
    out_json["datetime"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 保存到 MongoDB user_profiles 集合
    print("\n[5/5] 保存到 MongoDB...")
    db = get_mongo_db_sync()
    collection = db["user_profiles"]
    insert_result = collection.insert_one(out_json)
    print(f"      成功保存到 user_profiles, _id: {insert_result.inserted_id}")


if __name__ == "__main__":
    main()

