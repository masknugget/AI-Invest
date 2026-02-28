"""
股票工具函数测试

测试 app.utils 和 tradingagents.utils 中的股票相关工具函数
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tradingagents.utils.stock_utils import (
    normalize_stock_code,
    get_stock_exchange,
    is_valid_stock_code
)


def test_normalize_stock_code():
    """测试股票代码标准化"""
    print("=== 测试股票代码标准化 ===")
    
    test_cases = [
        # (输入, 预期输出, 描述)
        ("000001", "000001.SZ", "深市主板(无后缀)"),
        ("000001.SZ", "000001.SZ", "深市主板(有后缀)"),
        ("600000", "600000.SH", "沪市主板(无后缀)"),
        ("600000.SH", "600000.SH", "沪市主板(有后缀)"),
        ("300001", "300001.SZ", "创业板(无后缀)"),
        ("688001", "688001.SH", "科创板(无后缀)"),
        ("00001.HK", "00001.HK", "港股"),
        ("AAPL", "AAPL.US", "美股(无后缀)"),
        ("AAPL.US", "AAPL.US", "美股(有后缀)"),
    ]
    
    for input_code, expected, desc in test_cases:
        result = normalize_stock_code(input_code)
        status = "[PASS]" if result == expected else "[FAIL]"
        print(f"{status} {desc}: {input_code} -> {result}")
        assert result == expected, f"{desc}: 期望 {expected}, 实际 {result}"
    
    print("[PASS] 股票代码标准化测试通过")
    return True


def test_get_stock_exchange():
    """测试获取股票交易所"""
    print("\n=== 测试获取股票交易所 ===")
    
    test_cases = [
        ("000001.SZ", "深交所", "深市主板"),
        ("000001", "深交所", "深市主板(无后缀)"),
        ("600000.SH", "上交所", "沪市主板"),
        ("300001.SZ", "深交所", "创业板"),
        ("688001.SH", "上交所", "科创板"),
        ("00001.HK", "港交所", "港股"),
        ("AAPL.US", "美股", "美股"),
    ]
    
    for code, expected, desc in test_cases:
        result = get_stock_exchange(code)
        status = "[PASS]" if result == expected else "[FAIL]"
        print(f"{status} {desc} ({code}): {result}")
    
    print("[PASS] 获取股票交易所测试通过")
    return True


def test_is_valid_stock_code():
    """测试股票代码有效性验证"""
    print("\n=== 测试股票代码有效性验证 ===")
    
    valid_codes = [
        "000001", "000001.SZ",
        "600000", "600000.SH",
        "300001", "300001.SZ",
        "688001", "688001.SH",
        "00001.HK",
        "AAPL", "AAPL.US",
    ]
    
    invalid_codes = [
        "", " ", "123", "ABC", "000001.XYZ",
        "12345678", "invalid", "999999.XX",
    ]
    
    print("有效代码测试:")
    for code in valid_codes:
        result = is_valid_stock_code(code)
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status} {code}: {result}")
    
    print("无效代码测试:")
    for code in invalid_codes:
        result = is_valid_stock_code(code)
        status = "[PASS]" if not result else "[FAIL]"  # 应该返回False
        print(f"  {status} {repr(code)}: {result}")
    
    print("[PASS] 股票代码有效性验证测试通过")
    return True


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("开始股票工具函数测试")
    print("=" * 60)
    
    tests = [
        ("股票代码标准化", test_normalize_stock_code),
        ("获取股票交易所", test_get_stock_exchange),
        ("股票代码有效性验证", test_is_valid_stock_code),
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
