"""
Redis连接测试
"""

import redis


def test_redis_connection():
    """测试Redis连接"""
    client = redis.Redis(host='localhost', port=6379, socket_timeout=5)
    try:
        client.ping()
        print("✅ Redis连接成功")
        return True
    except Exception as e:
        print(f"❌ Redis连接失败: {e}")
        return False


if __name__ == "__main__":
    result = test_redis_connection()
    exit(0 if result else 1)
