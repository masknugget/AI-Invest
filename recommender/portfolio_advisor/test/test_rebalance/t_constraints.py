"""
调仓约束校验测试

测试 recommender.portfolio_advisor.rebalance.constraints 中的约束函数
"""
import importlib.util
import os
import warnings

import pandas as pd


# 直接加载目标模块，避免触发 recommender/__init__.py 中的大量依赖链
_project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)
_module_path = os.path.join(_project_root, "recommender", "portfolio_advisor", "rebalance", "constraints.py")
_spec = importlib.util.spec_from_file_location("rebalance_constraints", _module_path)
assert _spec is not None and _spec.loader is not None, f"无法加载模块: {_module_path}"
constraints = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(constraints)

clamp_max_actions = constraints.clamp_max_actions
count_overlap_days = constraints.count_overlap_days


def test_clamp_max_actions_normal():
    """测试 max_actions 在合法范围内直接返回"""
    print("\n=== 测试 clamp_max_actions 正常情况 ===")

    assert clamp_max_actions(2, 5) == 2, "max_actions=2, n_current=5 应返回 2"
    assert clamp_max_actions(1, 5) == 1, "max_actions=1, n_current=5 应返回 1"
    assert clamp_max_actions(3, 5) == 3, "max_actions=3, n_current=5 应返回 3"
    assert clamp_max_actions(2, 2) == 2, "max_actions=2, n_current=2 应返回 2"

    print("[PASS] 正常情况测试通过")
    return True


def test_clamp_max_actions_too_small():
    """测试 max_actions 小于 1 时抛出 ValueError"""
    print("\n=== 测试 clamp_max_actions 小于 1 ===")

    try:
        clamp_max_actions(0, 5)
        assert False, "max_actions=0 应抛出 ValueError"
    except ValueError as e:
        assert "max_actions 必须 >= 1" in str(e)
        print(f"[PASS] 正确抛出 ValueError: {e}")

    try:
        clamp_max_actions(-1, 5)
        assert False, "max_actions=-1 应抛出 ValueError"
    except ValueError as e:
        assert "max_actions 必须 >= 1" in str(e)
        print(f"[PASS] 正确抛出 ValueError: {e}")

    return True


def test_clamp_max_actions_exceeds_global_limit():
    """测试 max_actions 超过全局上限 3 时自动截断并告警"""
    print("\n=== 测试 clamp_max_actions 超过上限 3 ===")

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = clamp_max_actions(5, 10)

    assert result == 3, "max_actions=5 应被截断为 3"
    assert len(w) == 1, "应触发一次警告"
    assert "超过上限 3" in str(w[0].message)
    print(f"[PASS] 截断为 3，警告信息: {w[0].message}")

    return True


def test_clamp_max_actions_exceeds_portfolio_size():
    """测试 max_actions 大于当前组合标的数时自动截断并告警"""
    print("\n=== 测试 clamp_max_actions 超过当前标的数 ===")

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = clamp_max_actions(3, 2)

    assert result == 2, "max_actions=3, n_current=2 应被截断为 2"
    assert len(w) == 1, "应触发一次警告"
    assert "大于当前组合标的数" in str(w[0].message)
    print(f"[PASS] 截断为 2，警告信息: {w[0].message}")

    return True


def test_clamp_max_actions_both_limits():
    """测试 max_actions 同时超过全局上限和当前标的数时正确截断"""
    print("\n=== 测试 clamp_max_actions 同时超过两个限制 ===")

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = clamp_max_actions(10, 2)

    assert result == 2, "max_actions=10, n_current=2 最终应截断为 2"
    assert len(w) == 2, "应触发两次警告（先截断到 3，再截断到 2）"
    print(f"[PASS] 最终截断为 2，共触发 {len(w)} 次警告")

    return True


def test_count_overlap_days_basic():
    """测试多组合日期重叠计算"""
    print("\n=== 测试 count_overlap_days 基本情况 ===")

    df1 = pd.DataFrame({"date": ["2024-01-01", "2024-01-02", "2024-01-03"]})
    df2 = pd.DataFrame({"date": ["2024-01-02", "2024-01-03", "2024-01-04"]})
    df3 = pd.DataFrame({"date": ["2024-01-03", "2024-01-04", "2024-01-05"]})

    result = count_overlap_days([df1, df2, df3])
    assert result == 1, "三个组合共同交易日只有 2024-01-03"
    print(f"[PASS] 共同交易日数量: {result}")

    return True


def test_count_overlap_days_no_overlap():
    """测试无重叠日期时返回 0"""
    print("\n=== 测试 count_overlap_days 无重叠 ===")

    df1 = pd.DataFrame({"date": ["2024-01-01", "2024-01-02"]})
    df2 = pd.DataFrame({"date": ["2024-01-03", "2024-01-04"]})

    result = count_overlap_days([df1, df2])
    assert result == 0, "无共同交易日应返回 0"
    print("[PASS] 无重叠时返回 0")

    return True


def test_count_overlap_days_empty_list():
    """测试空列表时返回 0"""
    print("\n=== 测试 count_overlap_days 空列表 ===")

    result = count_overlap_days([])
    assert result == 0, "空列表应返回 0"
    print("[PASS] 空列表返回 0")

    return True


def test_count_overlap_days_single_df():
    """测试单个 DataFrame 时返回其日期数量"""
    print("\n=== 测试 count_overlap_days 单个 DataFrame ===")

    df1 = pd.DataFrame({"date": ["2024-01-01", "2024-01-02", "2024-01-03"]})

    result = count_overlap_days([df1])
    assert result == 3, "单个 DataFrame 应返回自身日期数量"
    print(f"[PASS] 单个 DataFrame 返回: {result}")

    return True


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("开始调仓约束校验测试")
    print("=" * 60)

    tests = [
        ("clamp_max_actions 正常情况", test_clamp_max_actions_normal),
        ("clamp_max_actions 小于 1", test_clamp_max_actions_too_small),
        ("clamp_max_actions 超过上限 3", test_clamp_max_actions_exceeds_global_limit),
        ("clamp_max_actions 超过当前标的数", test_clamp_max_actions_exceeds_portfolio_size),
        ("clamp_max_actions 同时超过两个限制", test_clamp_max_actions_both_limits),
        ("count_overlap_days 基本情况", test_count_overlap_days_basic),
        ("count_overlap_days 无重叠", test_count_overlap_days_no_overlap),
        ("count_overlap_days 空列表", test_count_overlap_days_empty_list),
        ("count_overlap_days 单个 DataFrame", test_count_overlap_days_single_df),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"\n[FAIL] {test_name} 测试失败: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"测试结果: 通过 {passed}, 失败 {failed}")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
