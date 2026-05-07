"""
查询推荐API示例

展示如何调用查询推荐接口 (app.routers.recommendation)
"""
import requests
import json

BASE_URL = "http://localhost:8000"
RECOMMEND_URL = f"{BASE_URL}/api/recommend-query"

TEST_USER = {"username": "admin", "password": "admin123"}


def get_token():
    """登录获取 Token"""
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json=TEST_USER,
        timeout=10
    )
    return resp.json()["data"]["access_token"]


# ------------------ 示例1: POST 推荐 ------------------
def example_post_recommend(token):
    print("=== POST 推荐相似问题 ===")
    payload = {
        "query": "摩根大通股价",
        "top_k": 3
    }
    resp = requests.post(
        f"{RECOMMEND_URL}/",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
        timeout=15
    )
    print(f"状态码: {resp.status_code}")
    if resp.status_code == 200:
        print(json.dumps(resp.json(), indent=2, ensure_ascii=False))
    else:
        print(resp.text[:200])


# ------------------ 示例2: GET 推荐 ------------------
def example_get_recommend(token):
    print("\n=== GET 推荐相似问题 ===")
    resp = requests.get(
        f"{RECOMMEND_URL}/",
        headers={"Authorization": f"Bearer {token}"},
        params={"q": "贵州茅台", "top_k": 5},
        timeout=15
    )
    print(f"状态码: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"原始查询: {data.get('original_query')}")
        print(f"推荐条数: {len(data.get('recommendations', []))}")
        for item in data.get("recommendations", [])[:3]:
            print(f"  - {item.get('query')} (score: {item.get('score')})")
    else:
        print(resp.text[:200])


# ------------------ 示例3: 统计信息 ------------------
def example_stats(token):
    print("\n=== 获取推荐集合统计 ===")
    resp = requests.get(
        f"{RECOMMEND_URL}/stats",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10
    )
    print(f"状态码: {resp.status_code}")
    if resp.status_code == 200:
        print(resp.json())
    else:
        print(resp.text[:200])


# ------------------ 示例4: 未认证访问 ------------------
def example_no_auth():
    print("\n=== 未携带 Token 访问 ===")
    resp = requests.post(
        f"{RECOMMEND_URL}/",
        json={"query": "测试", "top_k": 3},
        timeout=10
    )
    print(f"POST 无 Token: {resp.status_code} - {resp.text[:100]}")

    resp = requests.get(
        f"{RECOMMEND_URL}/stats",
        timeout=10
    )
    print(f"GET stats 无 Token: {resp.status_code} - {resp.text[:100]}")


# ------------------ 示例5: top_k 边界 ------------------
def example_top_k_boundary(token):
    print("\n=== top_k 边界测试 ===")
    for top_k in [1, 5, 20, 0, 25]:
        resp = requests.get(
            f"{RECOMMEND_URL}/",
            headers={"Authorization": f"Bearer {token}"},
            params={"q": "银行", "top_k": top_k},
            timeout=10
        )
        print(f"top_k={top_k}: {resp.status_code}")


# ------------------ 示例6: 通过 UUID 查询 QA 对 ------------------
def example_get_qa_by_uuid_success(token):
    """测试通过有效 UUID 查询 QA 对"""
    print("\n=== 通过 UUID 查询 QA 对 (成功) ===")
    # 使用一个已知的 UUID（来自 data_qa_5000.json 的第一条记录）
    test_uuid = "cf229763ecd14f71a1b887a89149c869"
    
    resp = requests.get(
        f"{RECOMMEND_URL}/qa/{test_uuid}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10
    )
    print(f"状态码: {resp.status_code}")
    
    if resp.status_code == 200:
        data = resp.json()
        print(f"[PASS] 查询成功")
        print(f"  UUID: {data.get('uuid')}")
        print(f"  Meta: {data.get('meta_data')}")
        print(f"  Query: {data.get('query')}")
        print(f"  Answer: {data.get('answer')[:50]}...")
        # 验证返回的数据结构
        assert "uuid" in data, "返回数据缺少 uuid 字段"
        assert "meta_data" in data, "返回数据缺少 meta_data 字段"
        assert "query" in data, "返回数据缺少 query 字段"
        assert "answer" in data, "返回数据缺少 answer 字段"
        assert data["uuid"] == test_uuid, "返回的 UUID 不匹配"
        return True
    else:
        print(f"[FAIL] 查询失败: {resp.text[:200]}")
        return False


def example_get_qa_by_uuid_not_found(token):
    """测试通过无效 UUID 查询（应返回 404）"""
    print("\n=== 通过 UUID 查询 QA 对 (不存在) ===")
    invalid_uuid = "00000000000000000000000000000000"
    
    resp = requests.get(
        f"{RECOMMEND_URL}/qa/{invalid_uuid}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10
    )
    print(f"状态码: {resp.status_code}")
    
    if resp.status_code == 404:
        print(f"[PASS] 正确返回 404")
        return True
    else:
        print(f"[FAIL] 应该返回 404，实际返回 {resp.status_code}")
        return False


def example_get_qa_by_uuid_no_auth():
    """测试未认证访问 UUID 查询接口"""
    print("\n=== 未携带 Token 访问 UUID 查询 ===")
    test_uuid = "cf229763ecd14f71a1b887a89149c869"
    
    resp = requests.get(
        f"{RECOMMEND_URL}/qa/{test_uuid}",
        timeout=10
    )
    print(f"状态码: {resp.status_code}")
    
    # 当前接口未启用认证，应该返回 200
    if resp.status_code == 200:
        print(f"[PASS] 无需认证即可访问 (接口当前未启用认证)")
        return True
    elif resp.status_code == 401:
        print(f"[PASS] 正确拒绝未认证访问")
        return True
    else:
        print(f"[INFO] 返回状态码: {resp.status_code}")
        return True


if __name__ == "__main__":
    print("确保服务已启动: python -m app.main")
    print("-" * 60)

    token = get_token()
    print(f"Token: {token[:30]}...\n")

    example_post_recommend(token)
    example_get_recommend(token)
    example_stats(token)
    example_no_auth()
    example_top_k_boundary(token)
    
    # 运行 UUID 查询测试
    example_get_qa_by_uuid_success(token)
    example_get_qa_by_uuid_not_found(token)
    example_get_qa_by_uuid_no_auth()

    print("\n=== 所有示例执行完毕 ===")
