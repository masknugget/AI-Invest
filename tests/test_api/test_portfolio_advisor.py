"""
投资组合顾问 API 测试

测试调仓管家相关接口，包括常用问题（FAQ）接口。
"""
import requests

BASE_URL = "http://localhost:8000"
PORTFOLIO_ENDPOINTS = {
    "faq": f"{BASE_URL}/api/v1/rebalance/faq",
}

# 测试用户
TEST_USER = {
    "username": "admin",
    "password": "admin123"
}


def get_auth_token():
    """获取认证 Token；若登录不可用则返回 dummy token（用于无认证测试服务器）。"""
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json=TEST_USER,
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            return data["data"]["access_token"]
    except Exception as e:
        print(f"获取 Token 失败，将使用 dummy token: {e}")
    return "dummy-token-for-testing"


def test_faq(token):
    """测试获取常用问题（FAQ）接口"""
    print("=== 测试获取常用问题 ===")

    if not token:
        print("[SKIP] 跳过测试: 没有可用的 Token")
        return False

    try:
        response = requests.get(
            PORTFOLIO_ENDPOINTS["faq"],
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )

        print(f"状态码: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                faq_list = data.get("data", {}).get("faq", [])
                print(f"[PASS] 获取常用问题成功")
                print(f"   问题数量: {len(faq_list)}")
                if faq_list:
                    print(f"   第一个问题: {faq_list[0].get('q', '')[:40]}...")
                    print(f"   第一个答案: {faq_list[0].get('anwser', '')[:40]}...")
                return True
            else:
                print(f"[FAIL] 业务失败: {data.get('message')}")
        else:
            print(f"[FAIL] 请求失败: {response.text}")

    except Exception as e:
        print(f"[FAIL] 请求异常: {e}")

    return False


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("开始投资组合顾问 API 测试")
    print(f"基础URL: {BASE_URL}")
    print("=" * 60)

    token = get_auth_token()
    if not token:
        print("[FAIL] 无法获取认证 Token，测试中止")
        return False

    if token == "dummy-token-for-testing":
        print("[INFO] 使用 dummy token（测试服务器未启用认证）\n")
    else:
        print("[PASS] 获取 Token 成功\n")

    passed = 0
    failed = 0

    if test_faq(token):
        passed += 1
    else:
        failed += 1

    print("\n" + "=" * 60)
    print(f"测试结果: 通过 {passed}, 失败 {failed}")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    print("确保服务已启动: python -m app.main")
    print("-" * 60)
    success = run_all_tests()
    exit(0 if success else 1)
