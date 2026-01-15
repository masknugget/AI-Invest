"""
Elasticsearch连接测试
"""

try:
    from elasticsearch import Elasticsearch
    ES_AVAILABLE = True
except ImportError:
    ES_AVAILABLE = False


def test_elasticsearch_connection():
    """测试Elasticsearch连接"""
    if not ES_AVAILABLE:
        print("⚠️ Elasticsearch库未安装，跳过测试")
        return True

    client = Elasticsearch(hosts=["http://localhost:9200"], request_timeout=5)
    try:
        if client.ping():
            print("✅ Elasticsearch连接成功")
            return True
        else:
            print("❌ Elasticsearch连接失败")
            return False
    except Exception as e:
        print(f"❌ Elasticsearch连接失败: {e}")
        return False


if __name__ == "__main__":
    result = test_elasticsearch_connection()
    exit(0 if result else 1)
