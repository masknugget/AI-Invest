"""
分析API测试

测试股票分析相关接口
"""
import requests
import time

BASE_URL = "http://localhost:8000"
ANALYSIS_ENDPOINTS = {
    "single": f"{BASE_URL}/api/analysis/single",
    "batch": f"{BASE_URL}/api/analysis/batch",
    "tasks": f"{BASE_URL}/api/analysis/tasks",
    "queue_status": f"{BASE_URL}/api/analysis/user/queue-status",
}

# 测试用户
TEST_USER = {
    "username": "admin",
    "password": "admin123"
}


def get_auth_token():
    """获取认证Token"""
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
        print(f"获取Token失败: {e}")
    return None


def test_submit_single_analysis(token):
    """测试提交单股分析"""
    print("=== 测试提交单股分析 ===")
    
    if not token:
        print("[SKIP] 跳过测试: 没有可用的 Token")
        return None
    
    payload = {
        "symbol": "000001.SZ",
        "parameters": {
            "market_type": "A股",
            "research_depth": "快速",
            "selected_analysts": ["market", "fundamentals"]
        }
    }
    
    try:
        response = requests.post(
            ANALYSIS_ENDPOINTS["single"],
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
            timeout=10
        )
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                task_id = data["data"]["task_id"]
                print(f"[PASS] 任务提交成功")
                print(f"   Task ID: {task_id}")
                print(f"   股票: {data['data'].get('symbol')}")
                return task_id
            else:
                print(f"[FAIL] 提交失败: {data.get('message')}")
        else:
            print(f"[FAIL] 请求失败: {response.text}")
            
    except Exception as e:
        print(f"[FAIL] 请求异常: {e}")
    
    return None


def test_get_task_status(token, task_id):
    """测试获取任务状态"""
    print(f"\n=== 测试获取任务状态 ===")
    
    if not token or not task_id:
        print("[SKIP] 跳过测试: 缺少 Token 或 Task ID")
        return False
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/analysis/tasks/{task_id}/status",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                status_data = data["data"]
                print(f"[PASS] 获取状态成功")
                print(f"   状态: {status_data.get('status')}")
                print(f"   进度: {status_data.get('progress')}%")
                return True
        
        print(f"[FAIL] 获取失败: {response.text}")
        return False
        
    except Exception as e:
        print(f"[FAIL] 请求异常: {e}")
        return False


def test_get_task_result(token, task_id):
    """测试获取任务结果"""
    print(f"\n=== 测试获取任务结果 ===")
    
    if not token or not task_id:
        print("[SKIP] 跳过测试: 缺少 Token 或 Task ID")
        return False
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/analysis/tasks/{task_id}/result",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                result = data["data"]
                print(f"[PASS] 获取结果成功")
                print(f"   股票: {result.get('stock_symbol')}")
                print(f"   摘要: {result.get('summary', '')[:50]}...")
                return True
            else:
                print(f"⏳ 结果尚未就绪: {data.get('message')}")
                return False
        elif response.status_code == 404:
            print(f"⏳ 结果尚未就绪或任务不存在")
            return False
        else:
            print(f"[FAIL] 请求失败: {response.text}")
            return False
            
    except Exception as e:
        print(f"[FAIL] 请求异常: {e}")
        return False


def test_list_user_tasks(token):
    """测试获取用户任务列表"""
    print("\n=== 测试获取用户任务列表 ===")
    
    if not token:
        print("[SKIP] 跳过测试: 没有可用的 Token")
        return False
    
    try:
        response = requests.get(
            ANALYSIS_ENDPOINTS["tasks"],
            headers={"Authorization": f"Bearer {token}"},
            params={"limit": 10},
            timeout=10
        )
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                tasks = data["data"]["tasks"]
                print(f"[PASS] 获取任务列表成功")
                print(f"   任务数量: {len(tasks)}")
                for task in tasks[:3]:  # 只显示前3个
                    print(f"   - {task.get('symbol')}: {task.get('status')}")
                return True
        
        print(f"[FAIL] 获取失败: {response.text}")
        return False
        
    except Exception as e:
        print(f"[FAIL] 请求异常: {e}")
        return False


def test_queue_status(token):
    """测试获取队列状态"""
    print("\n=== 测试获取队列状态 ===")
    
    if not token:
        print("[SKIP] 跳过测试: 没有可用的 Token")
        return False
    
    try:
        response = requests.get(
            ANALYSIS_ENDPOINTS["queue_status"],
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                status = data["data"]
                print(f"[PASS] 获取队列状态成功")
                print(f"   队列位置: {status.get('queue_position', 'N/A')}")
                print(f"   当前任务: {status.get('current_tasks', 'N/A')}")
                return True
        
        print(f"[FAIL] 获取失败: {response.text}")
        return False
        
    except Exception as e:
        print(f"[FAIL] 请求异常: {e}")
        return False


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("开始分析API测试")
    print(f"基础URL: {BASE_URL}")
    print("=" * 60)
    
    # 获取认证Token
    token = get_auth_token()
    if not token:
        print("[FAIL] 无法获取认证Token，测试中止")
        return
    
    print(f"[PASS] 获取Token成功\n")
    
    # 测试队列状态
    test_queue_status(token)
    
    # 测试提交单股分析
    task_id = test_submit_single_analysis(token)
    
    # 测试获取任务状态
    if task_id:
        test_get_task_status(token, task_id)
        # 注意: 结果可能还没生成好，这里只测试接口
        test_get_task_result(token, task_id)
    
    # 测试获取任务列表
    test_list_user_tasks(token)
    
    print("\n" + "=" * 60)
    print("分析API测试完成")
    print("=" * 60)


if __name__ == "__main__":
    print("确保服务已启动: python -m app.main")
    print("-" * 60)
    run_all_tests()
