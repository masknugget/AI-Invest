"""
分析工作流集成测试

测试完整的股票分析流程
注意: 此测试需要完整的系统环境，包括数据库和外部API
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 测试配置
TEST_STOCK = "000001.SZ"  # 平安银行
TEST_DATE = "2025-01-15"


def test_import_trading_graph():
    """测试导入交易图模块"""
    print("=== 测试导入交易图模块 ===")
    
    try:
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        print("[PASS] TradingAgentsGraph 导入成功")
        return True
    except ImportError as e:
        print(f"[FAIL] 导入失败: {e}")
        return False


def test_create_graph_instance():
    """测试创建图实例"""
    print("\n=== 测试创建图实例 ===")
    
    try:
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        from tradingagents.default_config import DEFAULT_CONFIG
        
        graph = TradingAgentsGraph(debug=True, config=DEFAULT_CONFIG.copy())
        print("[PASS] 图实例创建成功")
        return True
    except Exception as e:
        print(f"[FAIL] 创建失败: {e}")
        return False


def test_state_structure():
    """测试状态结构"""
    print("\n=== 测试状态结构 ===")
    
    try:
        from tradingagents.agents.utils.agent_states import InvestDebateState, RiskDebateState
        
        # 创建投资辩论状态
        invest_state = InvestDebateState({
            "history": "",
            "current_response": "",
            "count": 0
        })
        print(f"[PASS] InvestDebateState 创建成功: count={invest_state.count}")
        
        # 创建风险辩论状态
        risk_state = RiskDebateState({
            "history": "",
            "current_risky_response": "",
            "current_safe_response": "",
            "current_neutral_response": "",
            "count": 0
        })
        print(f"[PASS] RiskDebateState 创建成功: count={risk_state.count}")
        
        return True
    except Exception as e:
        print(f"[FAIL] 状态创建失败: {e}")
        return False


def test_analyst_creation():
    """测试分析师创建"""
    print("\n=== 测试分析师创建 ===")
    
    try:
        from tradingagents.agents.analysts.market_analyst import create_market_analyst
        from tradingagents.agents.analysts.fundamentals_analyst import create_fundamentals_analyst
        from tradingagents.llm_adapters import ChatDashScopeOpenAI
        
        # 注意: 这里只是测试导入和基本结构，实际需要API key
        print("[PASS] 分析师模块导入成功")
        print("  - market_analyst")
        print("  - fundamentals_analyst")
        
        return True
    except ImportError as e:
        print(f"[FAIL] 导入失败: {e}")
        return False


def test_stock_api():
    """测试股票API"""
    print("\n=== 测试股票API ===")
    
    try:
        from tradingagents.api.stock_api import get_stock_data
        
        print("[PASS] stock_api 模块导入成功")
        print("  - get_stock_data")
        
        return True
    except ImportError as e:
        print(f"[FAIL] 导入失败: {e}")
        return False


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("开始分析工作流集成测试")
    print("=" * 60)
    
    tests = [
        ("导入交易图模块", test_import_trading_graph),
        ("创建图实例", test_create_graph_instance),
        ("状态结构", test_state_structure),
        ("分析师创建", test_analyst_creation),
        ("股票API", test_stock_api),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            if result:
                passed += 1
            else:
                failed += 1
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
    print("注意: 此测试检查模块导入和基本结构")
    print("完整分析流程测试需要配置API密钥")
    print("-" * 60)
    success = run_all_tests()
    exit(0 if success else 1)
