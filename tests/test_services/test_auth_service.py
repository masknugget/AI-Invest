"""
认证服务测试

测试 app.services.auth 中的认证相关功能
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.services.auth.auth_service import AuthService


def test_create_access_token():
    """测试创建访问令牌"""
    print("=== 测试创建访问令牌 ===")
    
    # 创建Token
    token = AuthService.create_access_token(sub="test_user")
    
    assert token is not None, "Token 不应为 None"
    assert isinstance(token, str), "Token 应该是字符串"
    assert len(token) > 0, "Token 不应为空"
    
    print(f"[PASS] 创建Token成功: {token[:30]}...")
    return True


def test_verify_valid_token():
    """测试验证有效Token"""
    print("\n=== 测试验证有效Token ===")
    
    # 创建Token
    token = AuthService.create_access_token(sub="test_user")
    
    # 验证Token
    token_data = AuthService.verify_token(token)
    
    assert token_data is not None, "有效Token应该验证通过"
    assert token_data.sub == "test_user", "sub 应该匹配"
    
    print(f"[PASS] 验证Token成功: sub={token_data.sub}")
    return True


def test_verify_invalid_token():
    """测试验证无效Token"""
    print("\n=== 测试验证无效Token ===")
    
    # 验证无效Token
    token_data = AuthService.verify_token("invalid_token")
    assert token_data is None, "无效Token应该返回None"
    
    # 验证空Token
    token_data = AuthService.verify_token("")
    assert token_data is None, "空Token应该返回None"
    
    print("[PASS] 无效Token正确处理")
    return True


def test_token_expiration():
    """测试Token过期时间"""
    print("\n=== 测试Token过期时间 ===")
    
    # 创建短期Token (1秒过期)
    token = AuthService.create_access_token(sub="test_user", expires_delta=1)
    
    # 立即验证应该成功
    token_data = AuthService.verify_token(token)
    assert token_data is not None, "新Token应该有效"
    
    print("[PASS] Token过期时间测试通过")
    return True


def test_token_with_different_subjects():
    """测试不同用户名的Token"""
    print("\n=== 测试不同用户名的Token ===")
    
    users = ["user1", "user2", "admin", "test@example.com"]
    
    for user in users:
        token = AuthService.create_access_token(sub=user)
        token_data = AuthService.verify_token(token)
        
        assert token_data is not None, f"{user} 的Token应该有效"
        assert token_data.sub == user, f"sub 应该为 {user}"
        print(f"[PASS] {user}: Token创建并验证成功")
    
    return True


def test_hash_password():
    """测试密码哈希"""
    print("\n=== 测试密码哈希 ===")
    
    password = "my_secret_password"
    
    # 哈希密码
    hashed = AuthService.hash_password(password)
    
    assert hashed is not None, "哈希值不应为None"
    assert isinstance(hashed, str), "哈希值应为字符串"
    assert hashed != password, "哈希值应与原密码不同"
    
    print(f"[PASS] 密码哈希成功: {hashed[:30]}...")
    return True


def test_verify_password():
    """测试密码验证"""
    print("\n=== 测试密码验证 ===")
    
    password = "my_secret_password"
    wrong_password = "wrong_password"
    
    # 哈希密码
    hashed = AuthService.hash_password(password)
    
    # 验证正确密码
    is_valid = AuthService.verify_password(password, hashed)
    assert is_valid == True, "正确密码应该验证通过"
    print("[PASS] 正确密码验证通过")
    
    # 验证错误密码
    is_valid = AuthService.verify_password(wrong_password, hashed)
    assert is_valid == False, "错误密码应该验证失败"
    print("[PASS] 错误密码正确拒绝")
    
    return True


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("开始认证服务测试")
    print("=" * 60)
    
    tests = [
        ("创建访问令牌", test_create_access_token),
        ("验证有效Token", test_verify_valid_token),
        ("验证无效Token", test_verify_invalid_token),
        ("Token过期时间", test_token_expiration),
        ("不同用户名的Token", test_token_with_different_subjects),
        ("密码哈希", test_hash_password),
        ("密码验证", test_verify_password),
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
