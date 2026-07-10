"""
基于 dimension_scores 的调仓搜索测试（普通 Python 脚本，无需 pytest）。

覆盖 recommender.portfolio_advisor.rebalance.engine.suggest_rebalance_by_scores：
- 不依赖 DataFrame 的搜索流程
- 参数校验
- 结果按 improvement 降序

运行方式：
    python recommender/portfolio_advisor/test/test_rebalance/t_search_by_scores.py
"""

import os
import sys
import types

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

from recommender.portfolio_advisor.rebalance import suggest_rebalance_by_scores
from recommender.portfolio_advisor.rebalance.types import CandidatePool, RebalancePlan, StockCandidate


def _make_scores(drawdown: float, diversification: float, efficiency: float, stability: float, style: float) -> dict:
    """构造标准化五维得分字典。"""
    return {
        "drawdown_control": drawdown,
        "portfolio_diversification": diversification,
        "position_efficiency": efficiency,
        "return_stability": stability,
        "style_balance": style,
    }


def test_suggest_rebalance_by_scores_basic():
    """基于 dimension_scores 的搜索能返回方案。"""
    current_codes = ["A", "B"]
    current_weights = [0.5, 0.5]
    current_stock_scores = [
        _make_scores(60, 60, 60, 60, 60),
        _make_scores(60, 60, 60, 60, 60),
    ]

    candidates = [
        StockCandidate(code="X", df=None, dimension_scores=_make_scores(90, 90, 90, 90, 90)),
        StockCandidate(code="Y", df=None, dimension_scores=_make_scores(70, 70, 70, 70, 70)),
    ]
    pool = CandidatePool(candidates=candidates)

    plans = suggest_rebalance_by_scores(
        current_codes=current_codes,
        current_weights=current_weights,
        current_stock_scores=current_stock_scores,
        candidate_pool=pool,
        objective="composite_score",
        max_actions=1,
        min_improvement=0.0,
        weight_strategy="proportional",
        top_k=3,
    )

    assert isinstance(plans, list)
    assert len(plans) > 0
    for plan in plans:
        assert isinstance(plan, RebalancePlan)
        assert plan.objective == "composite_score"
        assert plan.improvement >= 0
    # 按 improvement 降序
    for i in range(1, len(plans)):
        assert plans[i].improvement <= plans[i - 1].improvement
    print("  [OK] test_suggest_rebalance_by_scores_basic 通过")


def test_suggest_rebalance_by_scores_min_improvement():
    """min_improvement 能过滤低提升方案。"""
    current_codes = ["A", "B"]
    current_weights = [0.5, 0.5]
    current_stock_scores = [
        _make_scores(80, 80, 80, 80, 80),
        _make_scores(80, 80, 80, 80, 80),
    ]

    candidates = [
        StockCandidate(code="X", df=None, dimension_scores=_make_scores(81, 81, 81, 81, 81)),
    ]
    pool = CandidatePool(candidates=candidates)

    plans = suggest_rebalance_by_scores(
        current_codes=current_codes,
        current_weights=current_weights,
        current_stock_scores=current_stock_scores,
        candidate_pool=pool,
        objective="composite_score",
        max_actions=1,
        min_improvement=10.0,  # 要求至少提升 10
        weight_strategy="proportional",
        top_k=3,
    )

    assert len(plans) == 0
    print("  [OK] test_suggest_rebalance_by_scores_min_improvement 通过")


def test_suggest_rebalance_by_scores_invalid_strategy():
    """不支持的权重策略应抛出 ValueError。"""
    current_codes = ["A"]
    current_weights = [1.0]
    current_stock_scores = [_make_scores(50, 50, 50, 50, 50)]
    pool = CandidatePool(candidates=[StockCandidate(code="X", df=None, dimension_scores=_make_scores(60, 60, 60, 60, 60))])

    try:
        suggest_rebalance_by_scores(
            current_codes=current_codes,
            current_weights=current_weights,
            current_stock_scores=current_stock_scores,
            candidate_pool=pool,
            weight_strategy="unknown_strategy",
        )
        raise AssertionError("应抛出 ValueError")
    except ValueError as e:
        assert "不支持的权重策略" in str(e)
    print("  [OK] test_suggest_rebalance_by_scores_invalid_strategy 通过")


def run_all_tests():
    """运行所有测试。"""
    tests = [
        ("suggest_rebalance_by_scores_basic", test_suggest_rebalance_by_scores_basic),
        ("suggest_rebalance_by_scores_min_improvement", test_suggest_rebalance_by_scores_min_improvement),
        ("suggest_rebalance_by_scores_invalid_strategy", test_suggest_rebalance_by_scores_invalid_strategy),
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
