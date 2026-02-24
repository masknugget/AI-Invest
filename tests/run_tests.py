#!/usr/bin/env python3
"""
测试运行器

运行所有测试模块并生成报告
"""
import os
import sys
import subprocess
import time
from pathlib import Path

# 测试模块配置
TEST_MODULES = {
    "核心模块": [
        "tests/test_core/test_config.py",
        "tests/test_core/test_response.py",
        "tests/test_core/test_rate_limiter.py",
    ],
    "服务层": [
        "tests/test_services/test_auth_service.py",
        "tests/test_services/test_trading_time.py",
    ],
    "工具函数": [
        "tests/test_utils/test_stock_utils.py",
    ],
    "数据流": [
        "tests/test_dataflows/test_data_source.py",
    ],
    "集成测试": [
        "tests/test_integration/test_analysis_workflow.py",
    ],
    "连接测试": [
        "tests/test_connect/test_mongo.py",
        "tests/test_connect/test_redis.py",
    ],
}


def run_test_file(test_file: str) -> dict:
    """运行单个测试文件"""
    result = {
        "file": test_file,
        "success": False,
        "output": "",
        "duration": 0
    }
    
    if not os.path.exists(test_file):
        result["output"] = f"文件不存在: {test_file}"
        return result
    
    start_time = time.time()
    
    try:
        # 运行测试文件
        process = subprocess.run(
            [sys.executable, test_file],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        
        result["duration"] = time.time() - start_time
        result["output"] = process.stdout
        
        if process.stderr:
            result["output"] += "\n[STDERR]\n" + process.stderr
        
        # 根据返回码判断成功/失败
        result["success"] = process.returncode == 0
        
    except subprocess.TimeoutExpired:
        result["output"] = "测试超时 (>60秒)"
        result["duration"] = time.time() - start_time
    except Exception as e:
        result["output"] = f"运行错误: {e}"
        result["duration"] = time.time() - start_time
    
    return result


def run_all_tests():
    """运行所有测试"""
    print("=" * 70)
    print("                    TradingAgents-CN 测试套件")
    print("=" * 70)
    
    total_tests = 0
    total_passed = 0
    total_failed = 0
    total_time = 0
    
    results_by_category = {}
    
    for category, test_files in TEST_MODULES.items():
        print(f"\n{'─' * 70}")
        print(f"【{category}】")
        print('─' * 70)
        
        category_results = []
        
        for test_file in test_files:
            total_tests += 1
            print(f"\n运行: {test_file}")
            
            result = run_test_file(test_file)
            category_results.append(result)
            
            # 显示结果
            status = "[PASS] 通过" if result["success"] else "[FAIL] 失败"
            print(f"结果: {status} ({result['duration']:.2f}s)")
            
            # 显示输出摘要
            if result["output"]:
                lines = result["output"].strip().split('\n')
                # 显示最后几行
                for line in lines[-10:]:
                    if line.strip():
                        print(f"  {line}")
            
            if result["success"]:
                total_passed += 1
            else:
                total_failed += 1
            
            total_time += result["duration"]
        
        results_by_category[category] = category_results
    
    # 打印汇总
    print("\n" + "=" * 70)
    print("                         测试汇总")
    print("=" * 70)
    
    for category, results in results_by_category.items():
        category_passed = sum(1 for r in results if r["success"])
        category_total = len(results)
        status = "[PASS]" if category_passed == category_total else "[SKIP]"
        print(f"{status} {category}: {category_passed}/{category_total} 通过")
    
    print("─" * 70)
    print(f"总计: {total_tests} 个测试, {total_passed} 通过, {total_failed} 失败")
    print(f"用时: {total_time:.2f} 秒")
    print("=" * 70)
    
    return total_failed == 0


def run_category_tests(category_tests):
    """运行指定类别的测试"""
    print("=" * 70)
    print(f"                    TradingAgents-CN 分类测试")
    print("=" * 70)
    
    total_tests = 0
    total_passed = 0
    total_failed = 0
    total_time = 0
    
    for category, test_files in category_tests.items():
        print(f"\n{'─' * 70}")
        print(f"【{category}】")
        print('─' * 70)
        
        for test_file in test_files:
            total_tests += 1
            print(f"\n运行: {test_file}")
            
            result = run_test_file(test_file)
            
            # 显示结果
            status = "[PASS] 通过" if result["success"] else "[FAIL] 失败"
            print(f"结果: {status} ({result['duration']:.2f}s)")
            
            # 显示输出摘要
            if result["output"]:
                lines = result["output"].strip().split('\n')
                for line in lines[-5:]:
                    if line.strip():
                        print(f"  {line}")
            
            if result["success"]:
                total_passed += 1
            else:
                total_failed += 1
            
            total_time += result["duration"]
    
    # 打印汇总
    print("\n" + "=" * 70)
    print("                         测试汇总")
    print("=" * 70)
    print(f"总计: {total_tests} 个测试, {total_passed} 通过, {total_failed} 失败")
    print(f"用时: {total_time:.2f} 秒")
    print("=" * 70)
    
    return total_failed == 0


def run_quick_tests():
    """运行快速测试 (不包括连接测试)"""
    print("=" * 70)
    print("                    TradingAgents-CN 快速测试")
    print("=" * 70)
    
    quick_modules = {
        k: v for k, v in TEST_MODULES.items() 
        if k != "连接测试"
    }
    
    total_tests = 0
    total_passed = 0
    total_failed = 0
    
    for category, test_files in quick_modules.items():
        print(f"\n【{category}】")
        
        for test_file in test_files:
            total_tests += 1
            print(f"  运行: {os.path.basename(test_file)}...", end=" ")
            
            result = run_test_file(test_file)
            
            if result["success"]:
                print(f"[PASS] ({result['duration']:.2f}s)")
                total_passed += 1
            else:
                print(f"[FAIL] ({result['duration']:.2f}s)")
                total_failed += 1
    
    print("\n" + "=" * 70)
    print(f"总计: {total_tests} 个测试, {total_passed} 通过, {total_failed} 失败")
    print("=" * 70)
    
    return total_failed == 0


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="TradingAgents-CN 测试运行器")
    parser.add_argument(
        "--quick", 
        action="store_true",
        help="运行快速测试 (不包括连接测试)"
    )
    parser.add_argument(
        "--category",
        choices=list(TEST_MODULES.keys()),
        help="运行特定类别的测试"
    )
    
    args = parser.parse_args()
    
    if args.category:
        # 运行特定类别
        print(f"运行类别: {args.category}")
        category_tests = {args.category: TEST_MODULES[args.category]}
        # 临时替换并运行
        success = run_category_tests(category_tests)
    elif args.quick:
        success = run_quick_tests()
    else:
        success = run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
