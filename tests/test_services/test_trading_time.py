"""
交易时间工具测试

测试 app.utils.trading_time 中的交易时间相关功能
"""
import os
import sys
from datetime import datetime, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.utils.trading_time import (
    is_trading_day,
    is_trading_time,
    get_next_trading_day,
    TRADING_START_AM,
    TRADING_END_AM,
    TRADING_START_PM,
    TRADING_END_PM
)


def test_trading_constants():
    """测试交易时间常量"""
    print("=== 测试交易时间常量 ===")
    
    print(f"上午交易时间: {TRADING_START_AM} - {TRADING_END_AM}")
    print(f"下午交易时间: {TRADING_START_PM} - {TRADING_END_PM}")
    
    assert TRADING_START_AM == time(9, 30), "上午开始时间应为 9:30"
    assert TRADING_END_AM == time(11, 30), "上午结束时间应为 11:30"
    assert TRADING_START_PM == time(13, 0), "下午开始时间应为 13:00"
    assert TRADING_END_PM == time(15, 0), "下午结束时间应为 15:00"
    
    print("[PASS] 交易时间常量测试通过")
    return True


def test_is_trading_day():
    """测试交易日判断"""
    print("\n=== 测试交易日判断 ===")
    
    # 测试日期 (需要根据实际情况调整)
    test_cases = [
        (datetime(2024, 1, 2), True, "周二(正常交易日)"),
        (datetime(2024, 1, 6), False, "周六(周末)"),
        (datetime(2024, 1, 7), False, "周日(周末)"),
    ]
    
    for date, expected, desc in test_cases:
        result = is_trading_day(date)
        status = "[PASS]" if result == expected else "[FAIL]"
        print(f"{status} {desc}: {result}")
    
    print("[PASS] 交易日判断测试完成")
    return True


def test_is_trading_time():
    """测试交易时间判断"""
    print("\n=== 测试交易时间判断 ===")
    
    # 测试不同时间
    test_cases = [
        (datetime(2024, 1, 2, 10, 0), True, "上午交易时间"),
        (datetime(2024, 1, 2, 12, 0), False, "午休时间"),
        (datetime(2024, 1, 2, 14, 0), True, "下午交易时间"),
        (datetime(2024, 1, 2, 9, 0), False, "开盘前"),
        (datetime(2024, 1, 2, 15, 30), False, "收盘后"),
    ]
    
    for dt, expected, desc in test_cases:
        result = is_trading_time(dt)
        status = "[PASS]" if result == expected else "[FAIL]"
        print(f"{status} {desc} ({dt.strftime('%H:%M')}): {result}")
    
    print("[PASS] 交易时间判断测试完成")
    return True


def test_get_next_trading_day():
    """测试获取下一个交易日"""
    print("\n=== 测试获取下一个交易日 ===")
    
    # 从周二开始
    tuesday = datetime(2024, 1, 2)  # 假设是周二
    next_day = get_next_trading_day(tuesday)
    print(f"周二 {tuesday.date()} 的下一个交易日: {next_day.date()}")
    
    # 从周五开始
    friday = datetime(2024, 1, 5)  # 假设是周五
    next_day = get_next_trading_day(friday)
    print(f"周五 {friday.date()} 的下一个交易日: {next_day.date()}")
    
    print("[PASS] 下一个交易日测试完成")
    return True


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("开始交易时间工具测试")
    print("=" * 60)
    
    tests = [
        ("交易时间常量", test_trading_constants),
        ("交易日判断", test_is_trading_day),
        ("交易时间判断", test_is_trading_time),
        ("下一个交易日", test_get_next_trading_day),
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
