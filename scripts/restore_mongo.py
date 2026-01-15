from pymongo import MongoClient
import json
import os
import bson.json_util


def restore_mongodb_with_python(
        backup_dir,
        host="localhost",
        port=27017,
        username=None,
        password=None
):
    """
    使用pymongo手动恢复所有数据库（从JSON文件）
    """

    # 检查备份目录
    if not os.path.exists(backup_dir):
        print(f"✗ 错误：备份目录不存在: {backup_dir}")
        return False

    # 连接MongoDB
    if username and password:
        uri = f"mongodb://{username}:{password}@{host}:{port}/"
        client = MongoClient(uri)
    else:
        client = MongoClient(host, port)

    print(f"开始从 {backup_dir} 恢复数据...")

    try:
        # 遍历备份目录中的所有数据库文件夹
        for db_name in os.listdir(backup_dir):
            db_path = os.path.join(backup_dir, db_name)

            # 跳过非目录项
            if not os.path.isdir(db_path):
                continue

            print(f"正在恢复数据库: {db_name}")
            db = client[db_name]

            # 遍历数据库目录中的所有集合文件
            for collection_file in os.listdir(db_path):
                if not collection_file.endswith('.json'):
                    continue

                collection_name = collection_file[:-5]  # 去掉.json后缀
                file_path = os.path.join(db_path, collection_file)

                print(f"  恢复集合: {collection_name}")

                # 读取JSON文件
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f, object_hook=bson.json_util.object_hook)

                # 清空集合并插入数据
                if data:
                    db[collection_name].delete_many({})  # 清空现有数据
                    db[collection_name].insert_many(data)

        print("✓ 所有数据恢复完成！")
        client.close()
        return True

    except Exception as e:
        print(f"✗ 恢复失败: {str(e)}")
        client.close()
        return False


# 使用示例
if __name__ == "__main__":
    restore_mongodb_with_python(
        backup_dir="mongodb_backup_20240101",
        # username="admin",  # 如果需要认证
        # password="your_password"
    )
