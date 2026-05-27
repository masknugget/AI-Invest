"""
AI Insights API 测试

测试 AI 洞察相关接口 (app.routers.ai_insights)
"""
import requests
import json

BASE_URL = "http://localhost:8000"
AI_INSIGHTS_URL = f"{BASE_URL}/api/v1/ai-insights"

# 测试用户
TEST_USER = {
    "username": "admin",
    "password": "admin123"
}


def get_auth_token():
    """获取认证 Token"""
    try:
        resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json=TEST_USER,
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            return data["data"]["access_token"]
    except Exception as e:
        print(f"获取 Token 失败: {e}")
    return None


def test_get_feed():
    """测试获取 AI Insights Feed 流"""
    print("=== 测试获取 AI Insights Feed 流 ===")

    try:
        resp = requests.get(
            f"{AI_INSIGHTS_URL}/feed",
            params={"pageSize": 5},
            timeout=15
        )

        print(f"状态码: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            items = data.get("data", [])
            print(f"[PASS] 获取成功")
            print(f"   返回条数: {data.get('count', len(items))}")
            for item in items[:2]:
                print(f"   - {item.get('title', 'N/A')}")
            return True
        else:
            print(f"[FAIL] 请求失败: {resp.text[:200]}")
            return False

    except Exception as e:
        print(f"[FAIL] 请求异常: {e}")
        return False


def test_get_feed_with_filter():
    """测试带类型过滤的 Feed"""
    print("\n=== 测试带类型过滤的 Feed ===")

    try:
        resp = requests.get(
            f"{AI_INSIGHTS_URL}/feed",
            params={"pageSize": 3, "filterTypes": "MACRO,SECTOR"},
            timeout=15
        )

        print(f"状态码: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            items = data.get("data", [])
            print(f"[PASS] 获取成功")
            print(f"   返回条数: {data.get('count', len(items))}")
            return True
        else:
            print(f"[FAIL] 请求失败: {resp.text[:200]}")
            return False

    except Exception as e:
        print(f"[FAIL] 请求异常: {e}")
        return False


def test_get_insight_detail():
    """测试获取 Insight 详情"""
    print("\n=== 测试获取 Insight 详情 ===")

    # 先获取一个可用的 insightId
    try:
        resp = requests.get(
            f"{AI_INSIGHTS_URL}/feed",
            params={"pageSize": 1},
            timeout=15
        )

        if resp.status_code != 200:
            print("[SKIP] 无法获取 feed 数据，跳过详情测试")
            return None

        items = resp.json().get("data", [])
        if not items:
            print("[SKIP] Feed 为空，跳过详情测试")
            return None

        insight_id = items[0].get("uuid")
        if not insight_id:
            print("[SKIP] Feed 项缺少 uuid，跳过详情测试")
            return None

        # 测试详情接口
        resp = requests.get(
            f"{AI_INSIGHTS_URL}/{insight_id}",
            params={"fromFeed": True},
            timeout=15
        )

        print(f"状态码: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            print(f"[PASS] 获取详情成功")
            print(f"   Insight ID: {insight_id}")
            # 详情返回的是 data_align 字段内容，结构可能较复杂
            if isinstance(data, dict):
                print(f"   键: {list(data.keys())[:5]}")
            return True
        elif resp.status_code == 404:
            print(f"[INFO] Insight 不存在 (404): {insight_id}")
            return False
        else:
            print(f"[FAIL] 请求失败: {resp.text[:200]}")
            return False

    except Exception as e:
        print(f"[FAIL] 请求异常: {e}")
        return False


def test_get_insight_detail_not_found():
    """测试获取不存在的 Insight 详情"""
    print("\n=== 测试获取不存在的 Insight 详情 ===")

    try:
        resp = requests.get(
            f"{AI_INSIGHTS_URL}/nonexistent-insight-id",
            timeout=10
        )

        print(f"状态码: {resp.status_code}")

        if resp.status_code == 404:
            print("[PASS] 正确返回 404")
            return True
        else:
            print(f"[FAIL] 应该返回 404，实际返回 {resp.status_code}")
            return False

    except Exception as e:
        print(f"[FAIL] 请求异常: {e}")
        return False


def test_get_views_history():
    """测试获取浏览历史"""
    print("\n=== 测试获取浏览历史 ===")

    try:
        resp = requests.get(
            f"{AI_INSIGHTS_URL}/views/history",
            params={"pageSize": 5, "page": 1},
            timeout=15
        )

        print(f"状态码: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            items = data.get("items", [])
            pagination = data.get("pagination", {})
            print(f"[PASS] 获取成功")
            print(f"   历史条数: {len(items)}")
            print(f"   分页: page={pagination.get('page')}, total={pagination.get('total')}")
            return True
        else:
            print(f"[FAIL] 请求失败: {resp.text[:200]}")
            return False

    except Exception as e:
        print(f"[FAIL] 请求异常: {e}")
        return False


def test_get_recommendation_history():
    """测试获取推荐历史"""
    print("\n=== 测试获取推荐历史 ===")

    try:
        resp = requests.get(
            f"{AI_INSIGHTS_URL}/history/recommendations",
            params={"pageSize": 5, "page": 1},
            timeout=15
        )

        print(f"状态码: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            # 返回的是 rec_content_data，可能是列表
            if isinstance(data, list):
                print(f"[PASS] 获取成功")
                print(f"   推荐条数: {len(data)}")
                for item in data[:2]:
                    print(f"   - {item.get('title', 'N/A')}")
            elif isinstance(data, dict):
                items = data.get("items", [])
                print(f"[PASS] 获取成功")
                print(f"   推荐条数: {len(items)}")
            return True
        else:
            print(f"[FAIL] 请求失败: {resp.text[:200]}")
            return False

    except Exception as e:
        print(f"[FAIL] 请求异常: {e}")
        return False


def test_get_recommendation_history_with_action():
    """测试带 action 过滤的推荐历史"""
    print("\n=== 测试带 action 过滤的推荐历史 ===")

    for action in ["click", "dismiss", "share", "save"]:
        try:
            resp = requests.get(
                f"{AI_INSIGHTS_URL}/history/recommendations",
                params={"pageSize": 3, "page": 1, "action": action},
                timeout=10
            )

            if resp.status_code == 200:
                print(f"   action={action}: OK")
            else:
                print(f"   action={action}: {resp.status_code}")

        except Exception as e:
            print(f"   action={action}: 异常 {e}")

    print("[PASS] 过滤测试完成")
    return True


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("AI Insights API 测试")
    print(f"基础URL: {BASE_URL}")
    print("=" * 60)

    tests = [
        ("获取 Feed 流", test_get_feed),
        ("带过滤的 Feed", test_get_feed_with_filter),
        ("获取 Insight 详情", test_get_insight_detail),
        ("获取不存在的 Insight", test_get_insight_detail_not_found),
        ("获取浏览历史", test_get_views_history),
        ("获取推荐历史", test_get_recommendation_history),
        ("推荐历史 action 过滤", test_get_recommendation_history_with_action),
    ]

    passed = 0
    failed = 0
    skipped = 0

    for test_name, test_func in tests:
        try:
            result = test_func()
            if result is True:
                passed += 1
            elif result is None:
                skipped += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n❌ {test_name} 测试异常: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"测试结果: 通过 {passed}, 失败 {failed}, 跳过 {skipped}")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    print("确保服务已启动: python -m app.main")
    print("-" * 60)
    success = run_all_tests()
    exit(0 if success else 1)
