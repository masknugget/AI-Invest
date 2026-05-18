import os
import json
import sys

# 添加项目根目录到 Python 路径，以便复用 app 配置和数据库连接
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from app.core.database import get_mongo_db_sync

path_dir = r'F:\work\report'


def load_dict(filename):
    """从 JSON 文件读取 dict"""
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)


data_out = []
for filename in os.listdir(path_dir):
    if str(filename).endswith(".json"):
        filename = os.path.join(path_dir, filename)
        data = load_dict(filename)
        data_out.append(data)

# 将数据逐条存入 MongoDB insight_news 集合
if data_out:
    db = get_mongo_db_sync()
    collection = db["insight_news"]
    inserted = 0
    failed = 0
    for item in data_out:
        try:
            collection.insert_one(item)
            inserted += 1
        except Exception as e:
            failed += 1
            print(f"插入失败: {e}")
    print(f"处理完成: 成功插入 {inserted} 条, 失败 {failed} 条")
else:
    print("没有数据需要插入")

