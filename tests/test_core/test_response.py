"""
响应格式测试

测试 app.core.response 中的统一响应格式
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.response import success_response, error_response


def test_success_response_basic():
    """测试基本成功响应"""
    print("=== 测试基本成功响应 ===")
    
    response = success_response(data={"key": "value"})
    
    assert response["success"] == True
    assert response["data"]["key"] == "value"
    assert response["message"] == ""
    
    print(f"响应: {response}")
    print("[PASS] 基本成功响应测试通过")
    return True


def test_success_response_with_message():
    """测试带消息的成功响应"""
    print("\n=== 测试带消息的成功响应 ===")
    
    response = success_response(
        data={"users": [1, 2, 3]},
        message="用户列表获取成功"
    )
    
    assert response["success"] == True
    assert response["message"] == "用户列表获取成功"
    assert len(response["data"]["users"]) == 3
    
    print(f"响应: {response}")
    print("[PASS] 带消息的成功响应测试通过")
    return True


def test_error_response_basic():
    """测试基本错误响应"""
    print("\n=== 测试基本错误响应 ===")
    
    response = error_response(message="操作失败")
    
    assert response["success"] == False
    assert response["message"] == "操作失败"
    assert response["code"] == 400
    
    print(f"响应: {response}")
    print("[PASS] 基本错误响应测试通过")
    return True


def test_error_response_with_code():
    """测试带错误码的错误响应"""
    print("\n=== 测试带错误码的错误响应 ===")
    
    test_cases = [
        (401, "未授权"),
        (403, "禁止访问"),
        (404, "资源不存在"),
        (500, "服务器错误"),
    ]
    
    for code, message in test_cases:
        response = error_response(message=message, code=code)
        assert response["code"] == code
        print(f"[PASS] 错误码 {code}: {message}")
    
    print("[PASS] 带错误码的错误响应测试通过")
    return True


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("开始响应格式测试")
    print("=" * 60)
    
    tests = [
        ("基本成功响应", test_success_response_basic),
        ("带消息的成功响应", test_success_response_with_message),
        ("基本错误响应", test_error_response_basic),
        ("带错误码的错误响应", test_error_response_with_code),
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
