"""
PostgreSQL连接测试
支持同步和异步两种测试方式
"""

import asyncio
import os
from typing import Optional, Dict, Any


# 同步测试 - 使用 psycopg2
def test_pgsql_connection_sync():
    """测试PostgreSQL同步连接"""
    try:
        import psycopg2
        from psycopg2 import OperationalError
    except ImportError:
        print("⚠️  psycopg2 未安装，跳过同步测试")
        return None

    # 从环境变量读取配置
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = int(os.getenv("POSTGRES_PORT", "5432"))
    database = os.getenv("POSTGRES_DATABASE", "tradingagents")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "")

    conn = None
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            connect_timeout=5  # 5秒超时
        )
        
        # 测试查询
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            version = cur.fetchone()
            print(f"✅ PostgreSQL同步连接成功")
            print(f"📊 服务器版本: {version[0]}")
            print(f"🔗 数据库: {database} @ {host}:{port}")
            return True
            
    except OperationalError as e:
        print(f"❌ PostgreSQL连接失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        return False
    finally:
        if conn:
            conn.close()


# 异步测试 - 使用 asyncpg
async def test_pgsql_connection_async():
    """测试PostgreSQL异步连接"""
    try:
        import asyncpg
    except ImportError:
        print("⚠️  asyncpg 未安装，跳过异步测试")
        return None

    # 从环境变量读取配置
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = int(os.getenv("POSTGRES_PORT", "5432"))
    database = os.getenv("POSTGRES_DATABASE", "tradingagents")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "")

    conn = None
    try:
        conn = await asyncpg.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            timeout=5  # 5秒超时
        )
        
        # 测试查询
        version = await conn.fetchrow("SELECT version();")
        print(f"✅ PostgreSQL异步连接成功")
        print(f"📊 服务器版本: {version['version']}")
        print(f"🔗 数据库: {database} @ {host}:{port}")
        return True
        
    except asyncpg.exceptions.ConnectionError as e:
        print(f"❌ PostgreSQL连接失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        return False
    finally:
        if conn:
            await conn.close()


def get_pgsql_config() -> Dict[str, Any]:
    """获取PostgreSQL配置信息"""
    return {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "database": os.getenv("POSTGRES_DATABASE", "tradingagents"),
        "user": os.getenv("POSTGRES_USER", "postgres"),
        "password": "***" if os.getenv("POSTGRES_PASSWORD") else "(未设置)",
        "ssl_mode": os.getenv("POSTGRES_SSL_MODE", "prefer"),
        "min_connections": int(os.getenv("POSTGRES_MIN_CONNECTIONS", "1")),
        "max_connections": int(os.getenv("POSTGRES_MAX_CONNECTIONS", "10"))
    }


def print_config():
    """打印PostgreSQL配置信息"""
    config = get_pgsql_config()
    print("📋 PostgreSQL 配置:")
    for key, value in config.items():
        print(f"  {key}: {value}")


async def run_all_tests():
    """运行所有测试"""
    print("🧪 PostgreSQL连接测试开始...")
    print("=" * 50)
    
    # 打印配置
    print_config()
    print("=" * 50)
    
    results = {}
    
    # 运行同步测试
    print("\n⚡ 运行同步连接测试...")
    results["sync"] = test_pgsql_connection_sync()
    
    # 运行异步测试
    print("\n⚡ 运行异步连接测试...")
    results["async"] = await test_pgsql_connection_async()
    
    # 打印总结
    print("\n" + "=" * 50)
    print("📊 测试总结:")
    for test_name, result in results.items():
        if result is None:
            status = "⚠️  跳过 (依赖未安装)"
        elif result:
            status = "✅ 通过"
        else:
            status = "❌ 失败"
        print(f"  {test_name}: {status}")
    
    # 返回总体结果
    all_passed = all(r for r in results.values() if r is not None)
    print("=" * 50)
    
    return all_passed


if __name__ == "__main__":
    # 检查环境变量
    required_vars = ["POSTGRES_PASSWORD"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print("⚠️  警告: 以下必需的环境变量未设置:")
        for var in missing_vars:
            print(f"  - {var}")
        print("\n请设置环境变量后再运行测试\n")
        print("示例:")
        print("  export POSTGRES_HOST=localhost")
        print("  export POSTGRES_PORT=5432")
        print("  export POSTGRES_DATABASE=tradingagents")
        print("  export POSTGRES_USER=postgres")
        print("  export POSTGRES_PASSWORD=your_password")
        print()
    
    # 运行测试
    result = asyncio.run(run_all_tests())
    exit(0 if result else 1)
