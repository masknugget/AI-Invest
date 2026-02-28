"""
配置模块测试

测试 app.core.config 中的配置加载和验证
"""
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.config import Settings, settings


def test_settings_singleton():
    """测试配置单例模式"""
    print("=== 测试配置单例模式 ===")
    
    # 验证 settings 是 Settings 的实例
    assert isinstance(settings, Settings), "settings 应该是 Settings 的实例"
    
    # 验证多次获取是同一个对象
    from app.core.config import settings as settings2
    assert settings is settings2, "settings 应该是单例"
    
    print("[PASS] 配置单例模式测试通过")
    return True


def test_mongodb_uri_building():
    """测试 MongoDB URI 构建"""
    print("\n=== 测试 MongoDB URI 构建 ===")
    
    # 测试无认证模式
    settings_no_auth = Settings(
        MONGODB_HOST="localhost",
        MONGODB_PORT=27017,
        MONGODB_DATABASE="test_db",
        MONGODB_USERNAME="",
        MONGODB_PASSWORD=""
    )
    expected_uri = "mongodb://localhost:27017/test_db"
    assert settings_no_auth.MONGO_URI == expected_uri, f"URI 不匹配: {settings_no_auth.MONGO_URI}"
    print(f"[PASS] 无认证 URI: {settings_no_auth.MONGO_URI}")
    
    # 测试有认证模式
    settings_with_auth = Settings(
        MONGODB_HOST="localhost",
        MONGODB_PORT=27017,
        MONGODB_DATABASE="test_db",
        MONGODB_USERNAME="admin",
        MONGODB_PASSWORD="password123",
        MONGODB_AUTH_SOURCE="admin"
    )
    expected_uri = "mongodb://admin:password123@localhost:27017/test_db?authSource=admin"
    assert settings_with_auth.MONGO_URI == expected_uri, f"URI 不匹配: {settings_with_auth.MONGO_URI}"
    print(f"[PASS] 有认证 URI: {settings_with_auth.MONGO_URI}")
    
    print("[PASS] MongoDB URI 构建测试通过")
    return True


def test_redis_url_building():
    """测试 Redis URL 构建"""
    print("\n=== 测试 Redis URL 构建 ===")
    
    # 测试无认证模式
    settings_no_auth = Settings(
        REDIS_HOST="localhost",
        REDIS_PORT=6379,
        REDIS_PASSWORD="",
        REDIS_DB=0
    )
    expected_url = "redis://localhost:6379/0"
    assert settings_no_auth.REDIS_URL == expected_url, f"URL 不匹配: {settings_no_auth.REDIS_URL}"
    print(f"[PASS] 无认证 URL: {settings_no_auth.REDIS_URL}")
    
    # 测试有认证模式
    settings_with_auth = Settings(
        REDIS_HOST="localhost",
        REDIS_PORT=6379,
        REDIS_PASSWORD="mypassword",
        REDIS_DB=1
    )
    expected_url = "redis://:mypassword@localhost:6379/1"
    assert settings_with_auth.REDIS_URL == expected_url, f"URL 不匹配: {settings_with_auth.REDIS_URL}"
    print(f"[PASS] 有认证 URL: {settings_with_auth.REDIS_URL}")
    
    print("[PASS] Redis URL 构建测试通过")
    return True


def test_default_values():
    """测试默认配置值"""
    print("\n=== 测试默认配置值 ===")
    
    default_settings = Settings()
    
    # 测试基础默认值
    assert default_settings.DEBUG == True, "DEBUG 默认值应为 True"
    assert default_settings.HOST == "0.0.0.0", "HOST 默认值应为 0.0.0.0"
    assert default_settings.PORT == 8000, "PORT 默认值应为 8000"
    
    # 测试数据库默认值
    assert default_settings.MONGODB_HOST == "localhost"
    assert default_settings.MONGODB_PORT == 27017
    assert default_settings.MONGODB_DATABASE == "tradingagents"
    
    # 测试 Redis 默认值
    assert default_settings.REDIS_HOST == "localhost"
    assert default_settings.REDIS_PORT == 6379
    
    # 测试 JWT 默认值
    assert default_settings.JWT_ALGORITHM == "HS256"
    assert default_settings.ACCESS_TOKEN_EXPIRE_MINUTES == 60
    
    print("[PASS] 默认配置值测试通过")
    return True


def test_is_production_property():
    """测试生产环境判断属性"""
    print("\n=== 测试生产环境判断属性 ===")
    
    # 测试开发环境
    dev_settings = Settings(DEBUG=True)
    assert dev_settings.is_production == False
    
    # 测试生产环境
    prod_settings = Settings(DEBUG=False)
    assert prod_settings.is_production == True
    
    print("[PASS] 生产环境判断属性测试通过")
    return True


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("开始配置模块测试")
    print("=" * 60)
    
    tests = [
        ("配置单例模式", test_settings_singleton),
        ("MongoDB URI 构建", test_mongodb_uri_building),
        ("Redis URL 构建", test_redis_url_building),
        ("默认配置值", test_default_values),
        ("生产环境判断属性", test_is_production_property),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"\n[FAIL] {test_name} 测试失败: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"测试结果: 通过 {passed}, 失败 {failed}")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
