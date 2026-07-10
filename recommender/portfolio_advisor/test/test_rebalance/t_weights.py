"""
权重再分配策略测试（普通 Python 脚本，无需 pytest）。

覆盖 recommender.portfolio_advisor.rebalance.weights 中的核心函数：
1. _normalize_weights：将权重归一化为加和等于 1。
2. redistribute_weights：通用权重再分配。
3. replace_stock：执行一次 1 对 1 替换。

运行方式：
    python recommender/portfolio_advisor/test/test_rebalance/t_weights.py
"""

import importlib.util
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

# 直接加载目标模块，避免触发 recommender/__init__.py 中的大量依赖链
_project_root = os.path.dirname(
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
)
_module_path = os.path.join(_project_root, "recommender", "portfolio_advisor", "rebalance", "weights.py")
_spec = importlib.util.spec_from_file_location("rebalance_weights", _module_path)
assert _spec is not None and _spec.loader is not None, f"无法加载模块: {_module_path}"
weights = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(weights)

WEIGHT_STRATEGIES = weights.WEIGHT_STRATEGIES
_normalize_weights = weights._normalize_weights
redistribute_weights = weights.redistribute_weights
replace_stock = weights.replace_stock
StockCandidate = weights.StockCandidate


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
    current = datetime(2023, 1, 2)
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
    return codes, dfs


def _make_candidate(code: str):
    """构造一个候选股票。"""
    dates = _make_dates(60)
    return StockCandidate(
        code=code,
        df=_make_df(code, dates, [100.0 + 0.8 * i for i in range(60)]),
        dimension_scores={},
    )


def test_weight_strategies_constant():
    """WEIGHT_STRATEGIES 集合包含预期策略。"""
    assert "proportional" in WEIGHT_STRATEGIES
    assert "equal" in WEIGHT_STRATEGIES
    assert "fixed_new_weight" in WEIGHT_STRATEGIES
    print("  [OK] test_weight_strategies_constant 通过")


def test_normalize_weights_basic():
    """_normalize_weights 将权重归一化为和为 1。"""
    normalized = _normalize_weights([1.0, 2.0, 3.0])
    assert abs(sum(normalized) - 1.0) < 1e-9
    assert abs(normalized[0] - 1.0 / 6.0) < 1e-9
    assert abs(normalized[1] - 2.0 / 6.0) < 1e-9
    assert abs(normalized[2] - 3.0 / 6.0) < 1e-9
    print("  [OK] test_normalize_weights_basic 通过")


def test_normalize_weights_zero_or_negative():
    """_normalize_weights 对非正权重和抛出 ValueError。"""
    for bad_weights in [[0.0, 0.0], [-1.0, 1.0], []]:
        try:
            _normalize_weights(bad_weights)
            raise AssertionError(f"应抛出 ValueError: {bad_weights}")
        except ValueError as e:
            assert "权重总和必须为正" in str(e)
    print("  [OK] test_normalize_weights_zero_or_negative 通过")


def test_redistribute_weights_proportional():
    """proportional 策略：调入标的均分调出权重。"""
    result = redistribute_weights(
        remaining_weights=[0.3, 0.2],
        n_new=2,
        total_removed_weight=0.5,
        weight_strategy="proportional",
        fixed_new_weight=0.0,
    )
    # 剩余 0.3/0.2 不变，新来两只各得 0.5/2=0.25
    assert result == [0.3, 0.2, 0.25, 0.25]
    print("  [OK] test_redistribute_weights_proportional 通过")


def test_redistribute_weights_equal():
    """equal 策略：所有标的等权。"""
    result = redistribute_weights(
        remaining_weights=[0.3, 0.2],
        n_new=2,
        total_removed_weight=0.5,
        weight_strategy="equal",
        fixed_new_weight=0.0,
    )
    # 共 4 只标的，每只 0.25
    assert result == [0.25, 0.25, 0.25, 0.25]
    print("  [OK] test_redistribute_weights_equal 通过")


def test_redistribute_weights_fixed_new_weight():
    """fixed_new_weight 策略：按固定权重分配。"""
    result = redistribute_weights(
        remaining_weights=[0.3, 0.2],
        n_new=2,
        total_removed_weight=0.5,
        weight_strategy="fixed_new_weight",
        fixed_new_weight=0.4,
    )
    # 新来两只共占 0.4，每只 0.2；剩余 0.5 按比例缩放为 0.6
    assert len(result) == 4
    assert abs(result[2] - 0.2) < 1e-9
    assert abs(result[3] - 0.2) < 1e-9
    assert abs(sum(result[:2]) - 0.6) < 1e-9
    print("  [OK] test_redistribute_weights_fixed_new_weight 通过")


def test_redistribute_weights_invalid_strategy():
    """不支持的权重策略应抛出 ValueError。"""
    try:
        redistribute_weights(
            remaining_weights=[0.3, 0.2],
            n_new=1,
            total_removed_weight=0.5,
            weight_strategy="unknown",
            fixed_new_weight=0.0,
        )
        raise AssertionError("应抛出 ValueError")
    except ValueError as e:
        assert "不支持的权重策略" in str(e)
    print("  [OK] test_redistribute_weights_invalid_strategy 通过")


def test_replace_stock_proportional():
    """replace_stock：proportional 策略替换后权重正确。"""
    codes, dfs = _make_portfolio()
    candidate = _make_candidate("X")

    new_codes, new_weights, new_dfs = replace_stock(
        codes,
        [0.4, 0.3, 0.2, 0.1],
        dfs,
        code_out="D",
        candidate=candidate,
        weight_strategy="proportional",
    )

    assert new_codes == ["A", "B", "C", "X"]
    assert len(new_weights) == 4
    assert len(new_dfs) == 4
    assert abs(sum(new_weights) - 1.0) < 1e-9
    assert abs(new_weights[0] - 0.4) < 1e-9
    assert abs(new_weights[1] - 0.3) < 1e-9
    assert abs(new_weights[2] - 0.2) < 1e-9
    assert abs(new_weights[3] - 0.1) < 1e-9
    print("  [OK] test_replace_stock_proportional 通过")


def test_replace_stock_equal():
    """replace_stock：equal 策略替换后等权。"""
    codes, dfs = _make_portfolio()
    candidate = _make_candidate("X")

    new_codes, new_weights, new_dfs = replace_stock(
        codes,
        [0.4, 0.3, 0.2, 0.1],
        dfs,
        code_out="A",
        candidate=candidate,
        weight_strategy="equal",
    )

    assert new_codes == ["B", "C", "D", "X"]
    assert len(new_weights) == 4
    assert abs(sum(new_weights) - 1.0) < 1e-9
    for w in new_weights:
        assert abs(w - 0.25) < 1e-9
    print("  [OK] test_replace_stock_equal 通过")


def test_replace_stock_fixed_new_weight():
    """replace_stock：fixed_new_weight 策略替换后固定权重正确。"""
    codes, dfs = _make_portfolio()
    candidate = _make_candidate("X")

    new_codes, new_weights, new_dfs = replace_stock(
        codes,
        [0.4, 0.3, 0.2, 0.1],
        dfs,
        code_out="A",
        candidate=candidate,
        weight_strategy="fixed_new_weight",
        fixed_new_weight=0.15,
    )

    assert new_codes == ["B", "C", "D", "X"]
    assert len(new_weights) == 4
    assert abs(sum(new_weights) - 1.0) < 1e-9
    idx = new_codes.index("X")
    assert abs(new_weights[idx] - 0.15) < 1e-9
    print("  [OK] test_replace_stock_fixed_new_weight 通过")


def test_replace_stock_invalid_strategy():
    """replace_stock：不支持的权重策略抛异常。"""
    codes, dfs = _make_portfolio()
    candidate = _make_candidate("X")

    try:
        replace_stock(
            codes,
            [0.4, 0.3, 0.2, 0.1],
            dfs,
            code_out="A",
            candidate=candidate,
            weight_strategy="unknown",
        )
        raise AssertionError("应抛出 ValueError")
    except ValueError as e:
        assert "不支持的权重策略" in str(e)
    print("  [OK] test_replace_stock_invalid_strategy 通过")


def test_replace_stock_code_out_not_found():
    """replace_stock：code_out 不在组合中抛异常。"""
    codes, dfs = _make_portfolio()
    candidate = _make_candidate("X")

    try:
        replace_stock(
            codes,
            [0.4, 0.3, 0.2, 0.1],
            dfs,
            code_out="Z",
            candidate=candidate,
            weight_strategy="proportional",
        )
        raise AssertionError("应抛出 ValueError")
    except ValueError as e:
        assert "不在当前组合中" in str(e)
    print("  [OK] test_replace_stock_code_out_not_found 通过")


def test_replace_stock_length_mismatch():
    """replace_stock：codes/weights/dfs 长度不一致抛异常。"""
    codes, dfs = _make_portfolio()
    candidate = _make_candidate("X")

    try:
        replace_stock(
            codes,
            [0.4, 0.3, 0.2],  # 长度不匹配
            dfs,
            code_out="A",
            candidate=candidate,
            weight_strategy="proportional",
        )
        raise AssertionError("应抛出 ValueError")
    except ValueError as e:
        assert "长度必须一致" in str(e)
    print("  [OK] test_replace_stock_length_mismatch 通过")


def run_all_tests():
    """运行所有测试。"""
    tests = [
        ("weight_strategies_constant", test_weight_strategies_constant),
        ("normalize_weights_basic", test_normalize_weights_basic),
        ("normalize_weights_zero_or_negative", test_normalize_weights_zero_or_negative),
        ("redistribute_weights_proportional", test_redistribute_weights_proportional),
        ("redistribute_weights_equal", test_redistribute_weights_equal),
        ("redistribute_weights_fixed_new_weight", test_redistribute_weights_fixed_new_weight),
        ("redistribute_weights_invalid_strategy", test_redistribute_weights_invalid_strategy),
        ("replace_stock_proportional", test_replace_stock_proportional),
        ("replace_stock_equal", test_replace_stock_equal),
        ("replace_stock_fixed_new_weight", test_replace_stock_fixed_new_weight),
        ("replace_stock_invalid_strategy", test_replace_stock_invalid_strategy),
        ("replace_stock_code_out_not_found", test_replace_stock_code_out_not_found),
        ("replace_stock_length_mismatch", test_replace_stock_length_mismatch),
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
