"""
调仓模块测试（普通 Python 脚本，无需 pytest）。

覆盖：
1. replace_stock 后权重归一化且总和为 1。
2. suggest_rebalance 返回的方案得分提升方向正确。
3. min_improvement 约束过滤生效。
4. load_candidate_pool_from_jsonl 对缺少 code 的数据报错。
5. 不同 objective 下 evaluate_portfolio 返回正确的目标得分。

运行方式：
    python recommender/portfolio_advisor/test/test_rebalance/test_rebalance.py
"""

import json
import os
import sys
import tempfile
import types
import warnings
from datetime import datetime, timedelta
from typing import List

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))

# mock openai，避免 recommender/__init__.py 链式导入失败
if "openai" not in sys.modules:
    _openai_mock = types.ModuleType("openai")
    _openai_mock.OpenAI = type("OpenAI", (), {})
    sys.modules["openai"] = _openai_mock

import pandas as pd

from recommender.portfolio_advisor.dimension.run import compute_portfolio_dimensions
from recommender.portfolio_advisor.rebalance import (
    CandidatePool,
    StockCandidate,
    load_candidate_pool_from_jsonl,
    suggest_rebalance,
)
from recommender.portfolio_advisor.rebalance.constraints import count_overlap_days
from recommender.portfolio_advisor.rebalance.scoring import (
    evaluate_portfolio,
    extract_objective_score,
)
from recommender.portfolio_advisor.rebalance.weights import replace_stock


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


def _make_stable_dates(n: int = 252) -> List[datetime]:
    """生成 n 个交易日日期（模拟，不含周末）。"""
    dates = []
    current = datetime(2023, 1, 2)
    while len(dates) < n:
        if current.weekday() < 5:
            dates.append(current)
        current += timedelta(days=1)
    return dates


def make_stable_dates():
    return _make_stable_dates(252)


def make_current_portfolio():
    """构造一个当前组合：4 只稳定股 + 1 只高波动差股。"""
    stable_dates = make_stable_dates()
    n = len(stable_dates)
    # 稳定缓慢上涨
    good_prices = [100.0 * (1 + 0.0003 * i) for i in range(n)]
    # 高波动、最终下跌
    bad_prices = [100.0 + 20.0 * (i % 10 - 5) - 0.2 * i for i in range(n)]

    codes = ["GOOD1", "GOOD2", "GOOD3", "GOOD4", "BAD1"]
    dfs = [
        _make_df("GOOD1", stable_dates, good_prices),
        _make_df("GOOD2", stable_dates, [p * 0.98 for p in good_prices]),
        _make_df("GOOD3", stable_dates, [p * 1.02 for p in good_prices]),
        _make_df("GOOD4", stable_dates, [p * 0.99 for p in good_prices]),
        _make_df("BAD1", stable_dates, bad_prices),
    ]
    weights = [0.2, 0.2, 0.2, 0.2, 0.2]
    return codes, weights, dfs


def make_candidate_pool():
    """构造候选池：1 只好股 + 1 只差股。"""
    stable_dates = make_stable_dates()
    n = len(stable_dates)
    good_prices = [100.0 * (1 + 0.0005 * i) for i in range(n)]
    bad_prices = [100.0 + 30.0 * (i % 8 - 4) - 0.3 * i for i in range(n)]

    candidates = [
        StockCandidate(
            code="CAND_GOOD",
            df=_make_df("CAND_GOOD", stable_dates, good_prices),
            dimension_scores={
                "drawdown_control": 80.0,
                "portfolio_diversification": 100.0,
                "position_efficiency": 80.0,
                "return_stability": 80.0,
                "style_balance": 0.0,
            },
        ),
        StockCandidate(
            code="CAND_BAD",
            df=_make_df("CAND_BAD", stable_dates, bad_prices),
            dimension_scores={
                "drawdown_control": 10.0,
                "portfolio_diversification": 100.0,
                "position_efficiency": 10.0,
                "return_stability": 20.0,
                "style_balance": 0.0,
            },
        ),
    ]
    return CandidatePool(candidates=candidates)


def test_count_overlap_days():
    _, _, dfs = make_current_portfolio()
    assert count_overlap_days(dfs) == len(dfs[0])
    print("  [OK] test_count_overlap_days 通过")


def test_replace_stock_weight_normalization():
    codes, weights, dfs = make_current_portfolio()
    candidate_pool = make_candidate_pool()
    candidate = candidate_pool.candidates[0]

    for strategy in ["proportional", "equal", "fixed_new_weight"]:
        kwargs = {}
        if strategy == "fixed_new_weight":
            kwargs["fixed_new_weight"] = 0.15

        new_codes, new_weights, new_dfs = replace_stock(
            codes, weights, dfs, "BAD1", candidate, weight_strategy=strategy, **kwargs
        )

        assert len(new_codes) == len(codes)
        assert len(new_weights) == len(weights)
        assert len(new_dfs) == len(dfs)
        assert abs(sum(new_weights) - 1.0) < 1e-9
        assert "BAD1" not in new_codes
        assert "CAND_GOOD" in new_codes
    print("  [OK] test_replace_stock_weight_normalization 通过")


def test_replace_stock_fixed_new_weight():
    codes, weights, dfs = make_current_portfolio()
    candidate_pool = make_candidate_pool()
    candidate = candidate_pool.candidates[0]

    new_codes, new_weights, new_dfs = replace_stock(
        codes, weights, dfs, "BAD1", candidate, weight_strategy="fixed_new_weight", fixed_new_weight=0.15
    )
    idx = new_codes.index("CAND_GOOD")
    assert abs(new_weights[idx] - 0.15) < 1e-9
    print("  [OK] test_replace_stock_fixed_new_weight 通过")


def test_evaluate_portfolio_objectives():
    codes, weights, dfs = make_current_portfolio()
    result = compute_portfolio_dimensions(dfs, weights)

    score_geo, _ = evaluate_portfolio(codes, weights, dfs, objective="geometric_composite_score")
    assert abs(score_geo - result.geometric_composite_score) < 1e-9

    score_arith, _ = evaluate_portfolio(codes, weights, dfs, objective="composite_score")
    assert abs(score_arith - result.composite_score) < 1e-9

    score_min, _ = evaluate_portfolio(codes, weights, dfs, objective="min_dimension_score")
    assert score_min == min(result.to_score_dict().values())

    score_dim, _ = evaluate_portfolio(codes, weights, dfs, objective="dimension:drawdown_control")
    assert abs(score_dim - result.drawdown_control.score) < 1e-9
    print("  [OK] test_evaluate_portfolio_objectives 通过")


def test_extract_objective_score_unknown():
    """测试 extract_objective_score 对未知目标抛出异常。"""
    dates = _make_stable_dates(60)
    dfs = [
        _make_df("ONLY1", dates, [100.0 + i for i in range(60)]),
        _make_df("ONLY2", dates, [100.0 + 0.5 * i for i in range(60)]),
    ]
    dims = compute_portfolio_dimensions(dfs, [0.5, 0.5])
    try:
        extract_objective_score(dims, "unknown_objective")
        raise AssertionError("应抛出 ValueError")
    except ValueError:
        pass
    print("  [OK] test_extract_objective_score_unknown 通过")


def test_suggest_rebalance_improvement_direction():
    _, weights, dfs = make_current_portfolio()
    candidate_pool = make_candidate_pool()

    plans = suggest_rebalance(
        dfs,
        weights,
        candidate_pool,
        objective="geometric_composite_score",
        max_actions=1,
        top_k=3,
        min_overlap_days=60,
    )

    assert len(plans) > 0
    best = plans[0]
    # 最优方案应推荐调入好股票
    assert any(action.code_in == "CAND_GOOD" for action in best.actions)
    # 得分应提升或至少不下降
    assert best.score_after >= best.score_before - 1e-9
    assert best.improvement >= -1e-9
    print("  [OK] test_suggest_rebalance_improvement_direction 通过")


def test_suggest_rebalance_min_improvement_filter():
    _, weights, dfs = make_current_portfolio()
    candidate_pool = make_candidate_pool()

    # 设置极高的最小提升阈值，应过滤掉所有方案
    plans = suggest_rebalance(
        dfs,
        weights,
        candidate_pool,
        objective="geometric_composite_score",
        max_actions=1,
        min_improvement=1_000_000.0,
        top_k=3,
        min_overlap_days=60,
    )
    assert len(plans) == 0
    print("  [OK] test_suggest_rebalance_min_improvement_filter 通过")


def test_suggest_rebalance_max_actions_clamping():
    _, weights, dfs = make_current_portfolio()
    candidate_pool = make_candidate_pool()

    # max_actions 超过当前组合大小应自动截断，不报错
    plans = suggest_rebalance(
        dfs,
        weights,
        candidate_pool,
        objective="geometric_composite_score",
        max_actions=10,
        top_k=3,
        min_overlap_days=60,
    )
    assert isinstance(plans, list)
    print("  [OK] test_suggest_rebalance_max_actions_clamping 通过")


def test_load_candidate_pool_from_jsonl_requires_code():
    data = [
        {"drawdown_control": 50.0, "portfolio_diversification": 100.0},
    ]
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps(item) + "\n")
        path = f.name

    try:
        try:
            load_candidate_pool_from_jsonl(path, require_code=True)
            raise AssertionError("应抛出 ValueError")
        except ValueError as e:
            assert "code" in str(e), f"错误信息不包含 'code': {e}"
    finally:
        os.unlink(path)
    print("  [OK] test_load_candidate_pool_from_jsonl_requires_code 通过")


def test_load_candidate_pool_from_jsonl_skip_missing_code():
    data = [
        {"code": "HAS_CODE", "drawdown_control": 50.0, "portfolio_diversification": 100.0},
        {"drawdown_control": 50.0, "portfolio_diversification": 100.0},
    ]
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps(item) + "\n")
        path = f.name

    try:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            candidates = load_candidate_pool_from_jsonl(path, require_code=False, fetch_full_df=False)
            # 无 code 且未拉取 df，结果为空
            assert len(candidates) == 0
            assert len(w) > 0 and issubclass(w[0].category, UserWarning), "应发出 UserWarning"
    finally:
        os.unlink(path)
    print("  [OK] test_load_candidate_pool_from_jsonl_skip_missing_code 通过")


def run_all_tests():
    """运行所有测试。"""
    tests = [
        ("test_count_overlap_days", test_count_overlap_days),
        ("test_replace_stock_weight_normalization", test_replace_stock_weight_normalization),
        ("test_replace_stock_fixed_new_weight", test_replace_stock_fixed_new_weight),
        ("test_evaluate_portfolio_objectives", test_evaluate_portfolio_objectives),
        ("test_extract_objective_score_unknown", test_extract_objective_score_unknown),
        ("test_suggest_rebalance_improvement_direction", test_suggest_rebalance_improvement_direction),
        ("test_suggest_rebalance_min_improvement_filter", test_suggest_rebalance_min_improvement_filter),
        ("test_suggest_rebalance_max_actions_clamping", test_suggest_rebalance_max_actions_clamping),
        ("test_load_candidate_pool_from_jsonl_requires_code", test_load_candidate_pool_from_jsonl_requires_code),
        ("test_load_candidate_pool_from_jsonl_skip_missing_code", test_load_candidate_pool_from_jsonl_skip_missing_code),
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
