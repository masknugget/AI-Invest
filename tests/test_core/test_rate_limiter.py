"""
速率限制测试

测试 app.core.rate_limiter 中的速率限制功能
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.rate_limiter import RateLimiter


def test_rate_limiter_init():
    """测试速率限制器初始化"""
    print("=== 测试速率限制器初始化 ===")
    
    limiter = RateLimiter(max_requests=10, window_seconds=60)
    
    assert limiter.max_requests == 10
    assert limiter.window_seconds == 60
    
    print("[PASS] 速率限制器初始化测试通过")
    return True


def test_rate_limiter_allow_request():
    """测试允许请求"""
    print("\n=== 测试允许请求 ===")
    
    limiter = RateLimiter(max_requests=5, window_seconds=60)
    user_id = "test_user_1"
    
    # 前 5 次请求应该被允许
    for i in range(5):
        result = limiter.allow_request(user_id)
        assert result == True, f"第 {i+1} 次请求应该被允许"
    
    print("[PASS] 允许请求测试通过")
    return True


def test_rate_limiter_exceeded():
    """测试超出限制"""
    print("\n=== 测试超出限制 ===")
    
    limiter = RateLimiter(max_requests=3, window_seconds=60)
    user_id = "test_user_2"
    
    # 前 3 次请求应该被允许
    for i in range(3):
        result = limiter.allow_request(user_id)
        assert result == True
    
    # 第 4 次请求应该被拒绝
    result = limiter.allow_request(user_id)
    assert result == False, "第 4 次请求应该被拒绝"
    
    print("[PASS] 超出限制测试通过")
    return True


def test_rate_limiter_different_users():
    """测试不同用户的限制隔离"""
    print("\n=== 测试不同用户的限制隔离 ===")
    
    limiter = RateLimiter(max_requests=3, window_seconds=60)
    user_a = "user_a"
    user_b = "user_b"
    
    # 用户 A 用完所有请求
    for i in range(3):
        limiter.allow_request(user_a)
    
    # 用户 A 应该被限制
    assert limiter.allow_request(user_a) == False
    
    # 用户 B 应该仍然可以请求
    for i in range(3):
        result = limiter.allow_request(user_b)
        assert result == True, f"用户 B 的第 {i+1} 次请求应该被允许"
    
    print("[PASS] 不同用户限制隔离测试通过")
    return True


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("开始速率限制测试")
    print("=" * 60)
    
    tests = [
        ("速率限制器初始化", test_rate_limiter_init),
        ("允许请求", test_rate_limiter_allow_request),
        ("超出限制", test_rate_limiter_exceeded),
        ("不同用户限制隔离", test_rate_limiter_different_users),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"\n[FAIL] {test_name} 测试失败: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"测试结果: 通过 {passed}, 失败 {failed}")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
