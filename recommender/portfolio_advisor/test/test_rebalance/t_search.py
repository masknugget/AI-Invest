"""
组合搜索测试（普通 Python 脚本，无需 pytest）。

覆盖 recommender.portfolio_advisor.rebalance.search 中的核心函数：
1. iter_replacement_candidates：枚举所有合法替换组合。
2. search_rebalance_plans：基于 dimension_scores 搜索并返回 RebalancePlan。

运行方式：
    python recommender/portfolio_advisor/test/test_rebalance/t_search.py
"""

import importlib.util
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

# 直接加载目标模块，避免触发 recommender/__init__.py 中的大量依赖链
_project_root = os.path.dirname(
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
)
_module_path = os.path.join(_project_root, "recommender", "portfolio_advisor", "rebalance", "search.py")
_spec = importlib.util.spec_from_file_location("rebalance_search", _module_path)
assert _spec is not None and _spec.loader is not None, f"无法加载模块: {_module_path}"
search = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(search)

iter_replacement_candidates = search.iter_replacement_candidates
search_rebalance_plans = search.search_rebalance_plans
CandidatePool = search.CandidatePool
StockCandidate = search.StockCandidate


class _FakePortfolioDimensions:
    """模拟 PortfolioDimensions。"""

    def __init__(self, name: str = "fake"):
        self.name = name

    def to_score_dict(self) -> dict:
        return {"fake": 50.0}


def _make_scores(drawdown: float, diversification: float, efficiency: float, stability: float, style: float) -> dict:
    """构造标准化五维得分字典。"""
    return {
        "drawdown_control": drawdown,
        "portfolio_diversification": diversification,
        "position_efficiency": efficiency,
        "return_stability": stability,
        "style_balance": style,
    }


def _make_small_portfolio():
    """构造小组合：2 只股票。"""
    codes = ["A", "B"]
    weights = [0.6, 0.4]
    scores = [
        _make_scores(60, 60, 60, 60, 60),
        _make_scores(60, 60, 60, 60, 60),
    ]
    return codes, weights, scores


def _make_small_candidate_pool():
    """构造小候选池：1 只股票。"""
    return CandidatePool(
        candidates=[
            StockCandidate(code="X", dimension_scores=_make_scores(70, 70, 70, 70, 70)),
        ]
    )


def _make_portfolio():
    """构造当前组合：3 只股票。"""
    codes = ["A", "B", "C"]
    weights = [0.4, 0.3, 0.3]
    scores = [
        _make_scores(60, 60, 60, 60, 60),
        _make_scores(60, 60, 60, 60, 60),
        _make_scores(60, 60, 60, 60, 60),
    ]
    return codes, weights, scores


def _make_candidate_pool():
    """构造候选池：2 只股票。"""
    return CandidatePool(
        candidates=[
            StockCandidate(code="X", dimension_scores=_make_scores(70, 70, 70, 70, 70)),
            StockCandidate(code="Y", dimension_scores=_make_scores(65, 65, 65, 65, 65)),
        ]
    )


def _mock_evaluate_portfolio_from_scores(score_current: float = 50.0, score_new: float = 60.0):
    """返回一个 mock 的 evaluate_portfolio_from_scores 函数。"""
    def evaluate_portfolio_from_scores(_codes, _scores, _weights, _objective=None):
        return score_new, _FakePortfolioDimensions("after")

    return evaluate_portfolio_from_scores


def test_iter_replacement_candidates_basic():
    """iter_replacement_candidates 枚举所有合法组合。"""
    results = list(iter_replacement_candidates(n_current=3, n_candidates=2, max_actions=2))

    # k=1: 3 个调出 × 2 个调入 = 6
    # k=2: C(3,2)=3 个调出 × C(2,2)=1 个调入 = 3
    assert len(results) == 9

    # 验证第一个和最后一个组合
    assert results[0] == ((0,), (0,))
    assert results[-1] == ((1, 2), (0, 1))
    print("  [OK] test_iter_replacement_candidates_basic 通过")


def test_iter_replacement_candidates_exceeds():
    """max_actions 超过实际可替换数量时自动截断。"""
    results = list(iter_replacement_candidates(n_current=2, n_candidates=1, max_actions=3))

    # 只能 k=1：2 个调出 × 1 个调入 = 2
    assert len(results) == 2
    assert results[0] == ((0,), (0,))
    assert results[1] == ((1,), (0,))
    print("  [OK] test_iter_replacement_candidates_exceeds 通过")


def test_search_rebalance_plans_basic():
    """search_rebalance_plans 返回按 improvement 降序排列的方案。"""
    codes, weights, scores = _make_small_portfolio()
    pool = _make_small_candidate_pool()
    portfolio_current = _FakePortfolioDimensions("before")

    # mock evaluate_portfolio_from_scores 使每个新组合都得 60 分
    setattr(
        search,
        "evaluate_portfolio_from_scores",
        _mock_evaluate_portfolio_from_scores(score_current=50.0, score_new=60.0),
    )

    plans = search_rebalance_plans(
        current_codes=codes,
        current_weights=weights,
        current_stock_scores=scores,
        candidate_pool=pool,
        score_current=50.0,
        portfolio_current=portfolio_current,
        objective="composite_score",
        max_actions=1,
        min_improvement=0.0,
        weight_strategy="proportional",
        fixed_new_weight=0.0,
        verbose=False,
    )

    # 2 个当前标的 × 1 个候选 = 2 个方案
    assert len(plans) == 2
    # improvement 均为 10.0
    for plan in plans:
        assert abs(plan.improvement - 10.0) < 1e-9
        assert plan.score_before == 50.0
        assert plan.score_after == 60.0
        assert plan.objective == "composite_score"
        assert len(plan.actions) == 1
        assert plan.actions[0].action_type == "replace"
    print("  [OK] test_search_rebalance_plans_basic 通过")


def test_search_rebalance_plans_sorted_by_improvement():
    """search_rebalance_plans 按 improvement 降序排列。"""
    codes, weights, scores = _make_small_portfolio()
    pool = _make_small_candidate_pool()
    portfolio_current = _FakePortfolioDimensions("before")

    score_counter = [50.0]

    def mock_evaluate_from_scores(_codes, _scores, _weights, _objective=None):
        score_counter[0] += 5.0
        return score_counter[0], _FakePortfolioDimensions("after")

    setattr(search, "evaluate_portfolio_from_scores", mock_evaluate_from_scores)

    plans = search_rebalance_plans(
        current_codes=codes,
        current_weights=weights,
        current_stock_scores=scores,
        candidate_pool=pool,
        score_current=50.0,
        portfolio_current=portfolio_current,
        objective="composite_score",
        max_actions=1,
        min_improvement=0.0,
        weight_strategy="proportional",
        fixed_new_weight=0.0,
        verbose=False,
    )

    assert len(plans) == 2
    for i in range(len(plans) - 1):
        assert plans[i].improvement >= plans[i + 1].improvement
    print("  [OK] test_search_rebalance_plans_sorted_by_improvement 通过")


def test_search_rebalance_plans_min_improvement():
    """min_improvement 过滤掉不满足条件的方案。"""
    codes, weights, scores = _make_small_portfolio()
    pool = _make_small_candidate_pool()
    portfolio_current = _FakePortfolioDimensions("before")

    setattr(
        search,
        "evaluate_portfolio_from_scores",
        _mock_evaluate_portfolio_from_scores(score_current=50.0, score_new=55.0),
    )

    plans = search_rebalance_plans(
        current_codes=codes,
        current_weights=weights,
        current_stock_scores=scores,
        candidate_pool=pool,
        score_current=50.0,
        portfolio_current=portfolio_current,
        objective="composite_score",
        max_actions=1,
        min_improvement=10.0,  # 要求至少提升 10
        weight_strategy="proportional",
        fixed_new_weight=0.0,
        verbose=False,
    )

    assert len(plans) == 0
    print("  [OK] test_search_rebalance_plans_min_improvement 通过")


def test_search_rebalance_plans_invalid_strategy():
    """不支持的权重策略应抛出 ValueError。"""
    codes, weights, scores = _make_small_portfolio()
    pool = _make_small_candidate_pool()
    portfolio_current = _FakePortfolioDimensions("before")

    try:
        search_rebalance_plans(
            current_codes=codes,
            current_weights=weights,
            current_stock_scores=scores,
            candidate_pool=pool,
            score_current=50.0,
            portfolio_current=portfolio_current,
            objective="composite_score",
            max_actions=1,
            min_improvement=0.0,
            weight_strategy="unknown_strategy",
            fixed_new_weight=0.0,
        )
        raise AssertionError("应抛出 ValueError")
    except ValueError as e:
        assert "不支持的权重策略" in str(e)
    print("  [OK] test_search_rebalance_plans_invalid_strategy 通过")


def test_search_rebalance_plans_max_actions_zero():
    """max_actions 小于 1 时不产生任何方案。"""
    codes, weights, scores = _make_small_portfolio()
    pool = _make_small_candidate_pool()
    portfolio_current = _FakePortfolioDimensions("before")

    setattr(
        search,
        "evaluate_portfolio_from_scores",
        _mock_evaluate_portfolio_from_scores(),
    )

    plans = search_rebalance_plans(
        current_codes=codes,
        current_weights=weights,
        current_stock_scores=scores,
        candidate_pool=pool,
        score_current=50.0,
        portfolio_current=portfolio_current,
        objective="composite_score",
        max_actions=0,
        min_improvement=0.0,
        weight_strategy="proportional",
        fixed_new_weight=0.0,
        verbose=False,
    )

    assert len(plans) == 0
    print("  [OK] test_search_rebalance_plans_max_actions_zero 通过")


def run_all_tests():
    """运行所有测试。"""
    tests = [
        ("iter_replacement_candidates_basic", test_iter_replacement_candidates_basic),
        ("iter_replacement_candidates_exceeds", test_iter_replacement_candidates_exceeds),
        ("search_rebalance_plans_basic", test_search_rebalance_plans_basic),
        ("search_rebalance_plans_sorted_by_improvement", test_search_rebalance_plans_sorted_by_improvement),
        ("search_rebalance_plans_min_improvement", test_search_rebalance_plans_min_improvement),
        ("search_rebalance_plans_invalid_strategy", test_search_rebalance_plans_invalid_strategy),
        ("search_rebalance_plans_max_actions_zero", test_search_rebalance_plans_max_actions_zero),
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
