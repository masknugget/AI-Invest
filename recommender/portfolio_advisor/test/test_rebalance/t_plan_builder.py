"""
调仓方案构造测试（普通 Python 脚本，无需 pytest）。

覆盖 recommender.portfolio_advisor.rebalance.plan_builder 的两个核心函数：
1. build_replacement_portfolio：根据调出/调入标的生成新组合。
2. make_actions：为一次替换生成可解释的 RebalanceAction 列表。

运行方式：
    python recommender/portfolio_advisor/test/test_rebalance/t_plan_builder.py
"""

import os
import sys
import types
from datetime import datetime, timedelta
from typing import List

# 添加项目根目录到路径
sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        )
    ),
)

# mock openai，避免 recommender/__init__.py 链式导入失败
if "openai" not in sys.modules:
    _openai_mock = types.ModuleType("openai")
    setattr(_openai_mock, "OpenAI", type("OpenAI", (), {}))
    sys.modules["openai"] = _openai_mock

import pandas as pd

from recommender.portfolio_advisor.rebalance.plan_builder import (
    build_replacement_portfolio,
    make_actions,
)
from recommender.portfolio_advisor.rebalance.types import StockCandidate


def _make_df(code: str, dates: List[datetime], prices: List[float]) -> pd.DataFrame:
    """构造包含必要列的合成行情 DataFrame。"""
    prices = [max(float(p), 1.0) for p in prices]
    pct_changes = [0.0] + [
        (prices[i] - prices[i - 1]) / prices[i - 1] for i in range(1, len(prices))
    ]
    return pd.DataFrame(
        {
            "date": [d.strftime("%Y-%m-%d") for d in dates],
            "code": [code] * len(dates),
            "open": prices,
            "high": prices,
            "low": prices,
            "close": prices,
            "preclose": [prices[0]] + prices[:-1],
            "pctChg": pct_changes,
            "volume": [1_000_000] * len(dates),
        }
    )


def _make_dates(n: int = 60) -> List[datetime]:
    """生成 n 个交易日日期（模拟，不含周末）。"""
    dates = []
    current = datetime(2024, 1, 2)
    while len(dates) < n:
        if current.weekday() < 5:
            dates.append(current)
        current += timedelta(days=1)
    return dates


def _make_portfolio():
    """构造一个 4 只股票的当前组合。"""
    dates = _make_dates(60)
    codes = ["A", "B", "C", "D"]
    dfs = [
        _make_df("A", dates, [100.0 + i for i in range(60)]),
        _make_df("B", dates, [100.0 + 0.5 * i for i in range(60)]),
        _make_df("C", dates, [100.0 + 0.3 * i for i in range(60)]),
        _make_df("D", dates, [100.0 + 0.1 * i for i in range(60)]),
    ]
    weights = [0.4, 0.3, 0.2, 0.1]
    return codes, weights, dfs


def _make_candidates():
    """构造两个调入候选股票。"""
    dates = _make_dates(60)
    return (
        StockCandidate(code="X", df=_make_df("X", dates, [100.0 + 0.8 * i for i in range(60)])),
        StockCandidate(code="Y", df=_make_df("Y", dates, [100.0 + 0.6 * i for i in range(60)])),
    )


def test_build_replacement_portfolio_proportional():
    """proportional 策略：调入标的均分调出权重，剩余标的权重不变。"""
    codes, weights, dfs = _make_portfolio()
    candidates = _make_candidates()

    new_codes, new_weights, new_dfs, removed_weight = build_replacement_portfolio(
        codes,
        weights,
        dfs,
        out_indices=(3,),  # 调出 D（权重 0.1）
        in_candidates=(candidates[0],),
        weight_strategy="proportional",
        fixed_new_weight=0.0,
    )

    assert new_codes == ["A", "B", "C", "X"]
    assert len(new_weights) == 4
    assert len(new_dfs) == 4
    assert abs(sum(new_weights) - 1.0) < 1e-9
    assert abs(removed_weight - 0.1) < 1e-9
    # A/B/C 权重保持原样（0.4/0.3/0.2），X 继承 D 的 0.1
    assert abs(new_weights[0] - 0.4) < 1e-9
    assert abs(new_weights[1] - 0.3) < 1e-9
    assert abs(new_weights[2] - 0.2) < 1e-9
    assert abs(new_weights[3] - 0.1) < 1e-9
    print("  [OK] test_build_replacement_portfolio_proportional 通过")


def test_build_replacement_portfolio_equal():
    """equal 策略：新组合所有标的等权。"""
    codes, weights, dfs = _make_portfolio()
    candidates = _make_candidates()

    new_codes, new_weights, new_dfs, removed_weight = build_replacement_portfolio(
        codes,
        weights,
        dfs,
        out_indices=(0,),  # 调出 A（权重 0.4）
        in_candidates=(candidates[0],),
        weight_strategy="equal",
        fixed_new_weight=0.0,
    )

    assert new_codes == ["B", "C", "D", "X"]
    assert len(new_weights) == 4
    assert abs(sum(new_weights) - 1.0) < 1e-9
    for w in new_weights:
        assert abs(w - 0.25) < 1e-9
    print("  [OK] test_build_replacement_portfolio_equal 通过")


def test_build_replacement_portfolio_fixed_new_weight():
    """fixed_new_weight 策略：调入标的按固定权重，剩余标的按比例缩放。"""
    codes, weights, dfs = _make_portfolio()
    candidates = _make_candidates()

    new_codes, new_weights, new_dfs, removed_weight = build_replacement_portfolio(
        codes,
        weights,
        dfs,
        out_indices=(0,),  # 调出 A（权重 0.4）
        in_candidates=(candidates[0],),
        weight_strategy="fixed_new_weight",
        fixed_new_weight=0.2,
    )

    assert new_codes == ["B", "C", "D", "X"]
    assert len(new_weights) == 4
    assert abs(sum(new_weights) - 1.0) < 1e-9
    assert abs(removed_weight - 0.4) < 1e-9
    # X 的权重为固定 0.2，其余按比例缩放
    assert abs(new_weights[new_codes.index("X")] - 0.2) < 1e-9
    print("  [OK] test_build_replacement_portfolio_fixed_new_weight 通过")


def test_build_replacement_portfolio_multiple_replacements():
    """一次调出两只、调入两只。"""
    codes, weights, dfs = _make_portfolio()
    candidates = _make_candidates()

    new_codes, new_weights, new_dfs, removed_weight = build_replacement_portfolio(
        codes,
        weights,
        dfs,
        out_indices=(0, 3),  # 调出 A(0.4) 和 D(0.1)
        in_candidates=candidates,
        weight_strategy="proportional",
        fixed_new_weight=0.0,
    )

    assert new_codes == ["B", "C", "X", "Y"]
    assert len(new_weights) == 4
    assert len(new_dfs) == 4
    assert abs(sum(new_weights) - 1.0) < 1e-9
    assert abs(removed_weight - 0.5) < 1e-9
    # B/C 权重不变
    assert abs(new_weights[0] - 0.3) < 1e-9
    assert abs(new_weights[1] - 0.2) < 1e-9
    # X/Y 均分调出权重 0.5 -> 各 0.25
    assert abs(new_weights[2] - 0.25) < 1e-9
    assert abs(new_weights[3] - 0.25) < 1e-9
    print("  [OK] test_build_replacement_portfolio_multiple_replacements 通过")


def test_build_replacement_portfolio_invalid_strategy():
    """不支持的权重策略应抛出 ValueError。"""
    codes, weights, dfs = _make_portfolio()
    candidates = _make_candidates()

    try:
        build_replacement_portfolio(
            codes,
            weights,
            dfs,
            out_indices=(0,),
            in_candidates=(candidates[0],),
            weight_strategy="unknown_strategy",
            fixed_new_weight=0.0,
        )
        raise AssertionError("应抛出 ValueError")
    except ValueError as e:
        assert "不支持的权重策略" in str(e)
    print("  [OK] test_build_replacement_portfolio_invalid_strategy 通过")


def test_make_actions_basic():
    """make_actions 生成正确数量的 RebalanceAction。"""
    codes = ["A", "B", "C", "D"]
    candidates = (
        StockCandidate(code="X", df=pd.DataFrame()),
        StockCandidate(code="Y", df=pd.DataFrame()),
    )
    new_weights = [0.3, 0.2, 0.25, 0.25]

    actions = make_actions(
        codes,
        out_indices=(0, 3),
        in_candidates=candidates,
        new_weights=new_weights,
        weight_strategy="proportional",
        improvement=0.05,
    )

    assert len(actions) == 2
    assert actions[0].action_type == "replace"
    assert actions[0].code_out == "A"
    assert actions[0].code_in == "X"
    assert actions[0].weight_in == 0.25
    assert actions[1].action_type == "replace"
    assert actions[1].code_out == "D"
    assert actions[1].code_in == "Y"
    assert actions[1].weight_in == 0.25
    reason = actions[0].reason
    assert reason is not None
    assert "0.0500" in reason
    assert "proportional" in reason or "继承调出权重" in reason
    print("  [OK] test_make_actions_basic 通过")


def test_make_actions_equal_strategy():
    """equal 策略时 reason 包含等权重说明。"""
    codes = ["A", "B"]
    candidates = (StockCandidate(code="X", df=pd.DataFrame()),)
    actions = make_actions(
        codes,
        out_indices=(0,),
        in_candidates=candidates,
        new_weights=[0.5, 0.5],
        weight_strategy="equal",
        improvement=0.01,
    )

    assert len(actions) == 1
    assert actions[0].code_out == "A"
    assert actions[0].code_in == "X"
    assert actions[0].weight_in == 0.5
    reason = actions[0].reason
    assert reason is not None
    assert "等权重再分配" in reason
    print("  [OK] test_make_actions_equal_strategy 通过")


def test_make_actions_fixed_new_weight_strategy():
    """fixed_new_weight 策略时 reason 包含固定权重说明。"""
    codes = ["A", "B"]
    candidates = (StockCandidate(code="X", df=pd.DataFrame()),)
    actions = make_actions(
        codes,
        out_indices=(0,),
        in_candidates=candidates,
        new_weights=[0.8, 0.2],
        weight_strategy="fixed_new_weight",
        improvement=0.02,
    )

    assert len(actions) == 1
    assert actions[0].weight_in == 0.2
    reason = actions[0].reason
    assert reason is not None
    assert "调入标的采用固定权重" in reason
    print("  [OK] test_make_actions_fixed_new_weight_strategy 通过")


def test_make_actions_more_out_than_in():
    """调出数量多于调入数量时，多余调出对应的 code_in/weight_in 为 None/0.0。"""
    codes = ["A", "B", "C"]
    candidates = (StockCandidate(code="X", df=pd.DataFrame()),)
    actions = make_actions(
        codes,
        out_indices=(0, 2),  # 调出 2 只
        in_candidates=candidates,  # 调入 1 只
        new_weights=[0.5, 0.2, 0.3],
        weight_strategy="proportional",
        improvement=0.01,
    )

    assert len(actions) == 2
    assert actions[0].code_out == "A"
    assert actions[0].code_in == "X"
    # n_remaining = 1，第一个调入标的对应 new_weights[1]
    assert actions[0].weight_in == 0.2
    assert actions[1].code_out == "C"
    assert actions[1].code_in is None
    assert actions[1].weight_in == 0.0
    print("  [OK] test_make_actions_more_out_than_in 通过")


def run_all_tests():
    """运行所有测试。"""
    tests = [
        ("build_replacement_portfolio_proportional", test_build_replacement_portfolio_proportional),
        ("build_replacement_portfolio_equal", test_build_replacement_portfolio_equal),
        ("build_replacement_portfolio_fixed_new_weight", test_build_replacement_portfolio_fixed_new_weight),
        ("build_replacement_portfolio_multiple_replacements", test_build_replacement_portfolio_multiple_replacements),
        ("build_replacement_portfolio_invalid_strategy", test_build_replacement_portfolio_invalid_strategy),
        ("make_actions_basic", test_make_actions_basic),
        ("make_actions_equal_strategy", test_make_actions_equal_strategy),
        ("make_actions_fixed_new_weight_strategy", test_make_actions_fixed_new_weight_strategy),
        ("make_actions_more_out_than_in", test_make_actions_more_out_than_in),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"\n  [FAIL] {test_name} 测试失败: {e}")
            failed += 1

    print(f"\n测试结果: 通过 {passed}, 失败 {failed}")
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
