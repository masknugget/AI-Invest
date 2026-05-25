import json

from app.core.database import get_mongo_db_sync


def load_dict(filename):
    """从 JSON 文件读取 dict"""
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)


p1 = r'F:\project_work\hf\AI-Invest\mock\mock_articles_001.json'
p2 = r'F:\project_work\hf\AI-Invest\mock\mock_articles_002.json'
p3 = r'F:\project_work\hf\AI-Invest\mock\mock_articles_003.json'
p4 = r'F:\project_work\hf\AI-Invest\mock\mock_articles_004.json'
p5 = r'F:\project_work\hf\AI-Invest\mock\mock_articles_005.json'


all_data = []
for i in [p1, p2, p3, p4, p5]:
    all_data.extend(load_dict(i))



db = get_mongo_db_sync()
collection = db["insight_agg"]
inserted = 0
failed = 0
for item in all_data:
    try:
        collection.insert_one(item)
        inserted += 1
    except Exception as e:
        failed += 1
        print(f"插入失败: {e}")
print(f"处理完成: 成功插入 {inserted} 条, 失败 {failed} 条")
