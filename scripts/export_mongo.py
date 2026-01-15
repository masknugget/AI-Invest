from pymongo import MongoClient
import json
import os
import bson.json_util
from datetime import datetime


def backup_mongodb_with_python(
        host="localhost",
        port=27017,
        username=None,
        password=None,
        output_dir=None
):
    """
    使用pymongo手动备份所有数据库
    """
    # 连接MongoDB
    if username and password:
        uri = f"mongodb://{username}:{password}@{host}:{port}/"
        client = MongoClient(uri)
    else:
        client = MongoClient(host, port)

    # 创建备份目录
    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"mongodb_backup_{timestamp}"

    os.makedirs(output_dir, exist_ok=True)
    print(f"开始备份到目录: {output_dir}")

    try:
        # 获取所有数据库名称（排除系统数据库）
        databases = [db for db in client.list_database_names() if db not in ['admin', 'local', 'config']]

        for db_name in databases:
            print(f"正在备份数据库: {db_name}")
            db = client[db_name]
            db_dir = os.path.join(output_dir, db_name)
            os.makedirs(db_dir, exist_ok=True)

            # 获取所有集合
            collections = db.list_collection_names()

            for collection_name in collections:
                print(f"  备份集合: {collection_name}")
                collection = db[collection_name]

                # 导出所有文档
                data = list(collection.find())

                # 保存为JSON文件（使用bson.json_util处理特殊类型）
                file_path = os.path.join(db_dir, f"{collection_name}.json")
                with open(file_path, 'w', encoding='utf-8') as f:
                    # 使用default参数处理ObjectId、Date等BSON类型
                    json.dump(data, f, default=bson.json_util.default, indent=2, ensure_ascii=False)

        print(f"✓ 备份完成！总数据库数: {len(databases)}")
        client.close()
        return output_dir

    except Exception as e:
        print(f"✗ 备份失败: {str(e)}")
        client.close()
        return None


# 使用示例
if __name__ == "__main__":
    backup_dir = backup_mongodb_with_python(
        host="localhost",
        port=27017,
        # username="admin",  # 如果需要认证
        # password="your_password"
    )