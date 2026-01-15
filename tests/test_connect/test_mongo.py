"""
MongoDB连接测试
"""

from pymongo import MongoClient


def test_mongodb_connection():
    """测试MongoDB连接"""
    client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=5000)
    try:
        client.admin.command('ping')
        print("✅ MongoDB连接成功")
        return True
    except Exception as e:
        print(f"❌ MongoDB连接失败: {e}")
        return False
    finally:
        client.close()


if __name__ == "__main__":
    result = test_mongodb_connection()
    exit(0 if result else 1)
