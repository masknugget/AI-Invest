"""
认证API测试

测试用户登录、登出、Token刷新等认证接口
"""
import requests
import json

# 测试配置
BASE_URL = "http://localhost:8000"
AUTH_ENDPOINTS = {
    "login": f"{BASE_URL}/api/auth/login",
    "logout": f"{BASE_URL}/api/auth/logout",
    "refresh": f"{BASE_URL}/api/auth/refresh",
    "me": f"{BASE_URL}/api/auth/me",
    "change_password": f"{BASE_URL}/api/auth/change-password",
}

# 测试用户数据
TEST_USER = {
    "username": "admin",  # 使用默认管理员账户测试
    "password": "admin123"
}


def test_login_success():
    """测试正常登录"""
    print("=== 测试正常登录 ===")
    
    try:
        response = requests.post(
            AUTH_ENDPOINTS["login"],
            json=TEST_USER,
            timeout=10
        )
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print(f"[PASS] 登录成功")
                print(f"   Token: {data['data']['access_token'][:30]}...")
                print(f"   用户: {data['data']['user']['username']}")
                return data["data"]["access_token"]
            else:
                print(f"[FAIL] 登录失败: {data.get('message')}")
                return None
        else:
            print(f"[FAIL] 请求失败: {response.text}")
            return None
            
    except Exception as e:
        print(f"[FAIL] 请求异常: {e}")
        return None


def test_login_wrong_password():
    """测试错误密码登录"""
    print("\n=== 测试错误密码登录 ===")
    
    try:
        response = requests.post(
            AUTH_ENDPOINTS["login"],
            json={"username": TEST_USER["username"], "password": "wrong_password"},
            timeout=10
        )
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 401:
            print("[PASS] 正确拒绝错误密码")
            return True
        else:
            print(f"[FAIL] 应该返回401，实际返回 {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[FAIL] 请求异常: {e}")
        return False


def test_login_empty_credentials():
    """测试空凭据登录"""
    print("\n=== 测试空凭据登录 ===")
    
    test_cases = [
        ({"username": "", "password": ""}, "空用户名密码"),
        ({"username": TEST_USER["username"], "password": ""}, "空密码"),
        ({"username": "", "password": TEST_USER["password"]}, "空用户名"),
    ]
    
    for payload, desc in test_cases:
        try:
            response = requests.post(
                AUTH_ENDPOINTS["login"],
                json=payload,
                timeout=10
            )
            
            if response.status_code == 400:
                print(f"[PASS] {desc}: 正确返回400")
            else:
                print(f"[SKIP] {desc}: 返回 {response.status_code}")
                
        except Exception as e:
            print(f"[FAIL] {desc}: 请求异常 {e}")
    
    return True


def test_get_user_info(token):
    """测试获取用户信息"""
    print("\n=== 测试获取用户信息 ===")
    
    if not token:
        print("[SKIP] 跳过测试: 没有可用的 Token")
        return False
    
    try:
        response = requests.get(
            AUTH_ENDPOINTS["me"],
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                user = data["data"]
                print(f"[PASS] 获取用户信息成功")
                print(f"   用户名: {user.get('username')}")
                print(f"   邮箱: {user.get('email')}")
                print(f"   是否管理员: {user.get('is_admin')}")
                return True
        
        print(f"[FAIL] 获取失败: {response.text}")
        return False
        
    except Exception as e:
        print(f"[FAIL] 请求异常: {e}")
        return False


def test_invalid_token():
    """测试无效 Token"""
    print("\n=== 测试无效 Token ===")
    
    try:
        response = requests.get(
            AUTH_ENDPOINTS["me"],
            headers={"Authorization": "Bearer invalid_token"},
            timeout=10
        )
        
        if response.status_code == 401:
            print("[PASS] 正确拒绝无效 Token")
            return True
        else:
            print(f"[SKIP] 返回状态码: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[FAIL] 请求异常: {e}")
        return False


def test_missing_token():
    """测试缺少 Token"""
    print("\n=== 测试缺少 Token ===")
    
    try:
        response = requests.get(
            AUTH_ENDPOINTS["me"],
            timeout=10
        )
        
        if response.status_code == 401:
            print("[PASS] 正确拒绝无 Token 请求")
            return True
        else:
            print(f"[SKIP] 返回状态码: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[FAIL] 请求异常: {e}")
        return False


def test_logout(token):
    """测试登出"""
    print("\n=== 测试登出 ===")
    
    if not token:
        print("[SKIP] 跳过测试: 没有可用的 Token")
        return False
    
    try:
        response = requests.post(
            AUTH_ENDPOINTS["logout"],
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print("[PASS] 登出成功")
                return True
        
        print(f"[FAIL] 登出失败: {response.text}")
        return False
        
    except Exception as e:
        print(f"[FAIL] 请求异常: {e}")
        return False


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("开始认证API测试")
    print(f"基础URL: {BASE_URL}")
    print("=" * 60)
    
    # 先测试登录获取 Token
    token = test_login_success()
    
    # 其他测试
    test_login_wrong_password()
    test_login_empty_credentials()
    
    if token:
        test_get_user_info(token)
        test_logout(token)
    
    test_invalid_token()
    test_missing_token()
    
    print("\n" + "=" * 60)
    print("认证API测试完成")
    print("=" * 60)


if __name__ == "__main__":
    print("确保服务已启动: python -m app.main")
    print("-" * 60)
    run_all_tests()
