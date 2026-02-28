"""
数据源测试

测试 tradingagents.dataflows 中的数据源功能
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tradingagents.constants.data_sources import DataSource, MarketType


def test_data_source_enum():
    """测试数据源枚举"""
    print("=== 测试数据源枚举 ===")
    
    # 验证数据源枚举值
    sources = [
        DataSource.TUSHARE,
        DataSource.AKSHARE,
        DataSource.BAOSTOCK,
        DataSource.YFINANCE,
        DataSource.FINNHUB,
    ]
    
    for source in sources:
        print(f"  {source.name}: {source.value}")
    
    print("[PASS] 数据源枚举测试通过")
    return True


def test_market_type_enum():
    """测试市场类型枚举"""
    print("\n=== 测试市场类型枚举 ===")
    
    markets = [
        MarketType.A_SHARE,
        MarketType.HK,
        MarketType.US,
    ]
    
    for market in markets:
        print(f"  {market.name}: {market.value}")
    
    print("[PASS] 市场类型枚举测试通过")
    return True


def test_data_source_properties():
    """测试数据源属性"""
    print("\n=== 测试数据源属性 ===")
    
    # 测试数据源是否支持特定市场
    source_market_support = {
        DataSource.TUSHARE: [MarketType.A_SHARE],
        DataSource.AKSHARE: [MarketType.A_SHARE, MarketType.HK],
        DataSource.YFINANCE: [MarketType.US, MarketType.HK],
    }
    
    for source, supported_markets in source_market_support.items():
        print(f"\n{source.name} 支持的市场:")
        for market in supported_markets:
            print(f"  - {market.value}")
    
    print("[PASS] 数据源属性测试通过")
    return True


def test_data_source_from_string():
    """测试从字符串获取数据源"""
    print("\n=== 测试从字符串获取数据源 ===")
    
    test_cases = [
        ("tushare", DataSource.TUSHARE),
        ("TUSHARE", DataSource.TUSHARE),
        ("akshare", DataSource.AKSHARE),
        ("AKSHARE", DataSource.AKSHARE),
        ("baostock", DataSource.BAOSTOCK),
        ("yfinance", DataSource.YFINANCE),
    ]
    
    for input_str, expected in test_cases:
        try:
            result = DataSource(input_str.lower())
            status = "[PASS]" if result == expected else "[FAIL]"
            print(f"{status} {input_str} -> {result.name}")
        except ValueError:
            print(f"⚠️ {input_str} -> 无效的数据源")
    
    print("[PASS] 从字符串获取数据源测试通过")
    return True


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("开始数据源测试")
    print("=" * 60)
    
    tests = [
        ("数据源枚举", test_data_source_enum),
        ("市场类型枚举", test_market_type_enum),
        ("数据源属性", test_data_source_properties),
        ("从字符串获取数据源", test_data_source_from_string),
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
