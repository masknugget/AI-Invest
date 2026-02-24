"""
股票数据API测试

测试股票基础数据、行情数据等相关接口
"""
import requests

BASE_URL = "http://localhost:8000"

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


def test_search_stocks(token):
    """测试股票搜索"""
    print("=== 测试股票搜索 ===")
    
    if not token:
        print("[SKIP] 跳过测试: 没有可用的 Token")
        return False
    
    # 测试不同的搜索关键词
    search_keywords = ["平安", "000001", "银行", "科技"]
    
    for keyword in search_keywords:
        try:
            response = requests.get(
                f"{BASE_URL}/api/stocks/search",
                headers={"Authorization": f"Bearer {token}"},
                params={"q": keyword, "limit": 5},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    stocks = data.get("data", [])
                    print(f"[PASS] 搜索'{keyword}': 找到 {len(stocks)} 个结果")
                else:
                    print(f"[SKIP] 搜索'{keyword}': {data.get('message')}")
            else:
                print(f"[FAIL] 搜索'{keyword}': 状态码 {response.status_code}")
                
        except Exception as e:
            print(f"[FAIL] 搜索'{keyword}': 请求异常 {e}")
    
    return True


def test_get_stock_detail(token):
    """测试获取股票详情"""
    print("\n=== 测试获取股票详情 ===")
    
    if not token:
        print("[SKIP] 跳过测试: 没有可用的 Token")
        return False
    
    # 测试股票代码
    test_symbols = ["000001.SZ", "600000.SH", "000858.SZ"]
    
    for symbol in test_symbols:
        try:
            response = requests.get(
                f"{BASE_URL}/api/stocks/{symbol}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    stock = data.get("data", {})
                    print(f"[PASS] {symbol}: {stock.get('name', 'N/A')} - {stock.get('industry', 'N/A')}")
                else:
                    print(f"[SKIP] {symbol}: {data.get('message')}")
            elif response.status_code == 404:
                print(f"[SKIP] {symbol}: 股票不存在")
            else:
                print(f"[FAIL] {symbol}: 状态码 {response.status_code}")
                
        except Exception as e:
            print(f"[FAIL] {symbol}: 请求异常 {e}")
    
    return True


def test_get_stock_quotes(token):
    """测试获取股票行情"""
    print("\n=== 测试获取股票行情 ===")
    
    if not token:
        print("[SKIP] 跳过测试: 没有可用的 Token")
        return False
    
    symbols = ["000001.SZ", "600000.SH"]
    
    for symbol in symbols:
        try:
            response = requests.get(
                f"{BASE_URL}/api/stocks/{symbol}/quotes",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    quote = data.get("data", {})
                    print(f"[PASS] {symbol}: 价格 {quote.get('price', 'N/A')}, 涨跌 {quote.get('change_percent', 'N/A')}%")
                else:
                    print(f"[SKIP] {symbol}: {data.get('message')}")
            else:
                print(f"[FAIL] {symbol}: 状态码 {response.status_code}")
                
        except Exception as e:
            print(f"[FAIL] {symbol}: 请求异常 {e}")
    
    return True


def test_get_stock_history(token):
    """测试获取历史数据"""
    print("\n=== 测试获取历史数据 ===")
    
    if not token:
        print("[SKIP] 跳过测试: 没有可用的 Token")
        return False
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/stocks/000001.SZ/history",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "start_date": "2024-01-01",
                "end_date": "2024-01-31"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                history = data.get("data", [])
                print(f"[PASS] 获取历史数据成功: {len(history)} 条记录")
                if history:
                    print(f"   最新: {history[-1].get('date')} - 收盘 {history[-1].get('close')}")
                return True
            else:
                print(f"[SKIP] {data.get('message')}")
        else:
            print(f"[FAIL] 状态码 {response.status_code}")
            
    except Exception as e:
        print(f"[FAIL] 请求异常 {e}")
    
    return False


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("开始股票数据API测试")
    print(f"基础URL: {BASE_URL}")
    print("=" * 60)
    
    # 获取认证Token
    token = get_auth_token()
    if not token:
        print("[FAIL] 无法获取认证Token，测试中止")
        return
    
    print(f"[PASS] 获取Token成功\n")
    
    # 运行测试
    test_search_stocks(token)
    test_get_stock_detail(token)
    test_get_stock_quotes(token)
    test_get_stock_history(token)
    
    print("\n" + "=" * 60)
    print("股票数据API测试完成")
    print("=" * 60)


if __name__ == "__main__":
    print("确保服务已启动: python -m app.main")
    print("-" * 60)
    run_all_tests()
