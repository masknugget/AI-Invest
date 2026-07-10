"""
调仓建议引擎测试（普通 Python 脚本，无需 pytest）。

覆盖 recommender.portfolio_advisor.rebalance.engine.suggest_rebalance：
- 参数校验
- max_actions 截断
- 基于 stock_dimension_scores.jsonl 的优化流程

运行方式：
    python recommender/portfolio_advisor/test/test_rebalance/t_engine.py
"""

import json
import os
import sys
import tempfile
import types
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

from recommender.portfolio_advisor.rebalance import engine, search as search_module
from recommender.portfolio_advisor.rebalance.types import RebalancePlan


def _make_scores(drawdown: float, diversification: float, efficiency: float, stability: float, style: float) -> dict:
    """构造标准化五维得分字典。"""
    return {
        "drawdown_control": drawdown,
        "portfolio_diversification": diversification,
        "position_efficiency": efficiency,
        "return_stability": stability,
        "style_balance": style,
    }


def _make_scores_path(codes: List[str], candidate_codes: List[str]) -> str:
    """创建临时 stock_dimension_scores.jsonl 文件，返回路径。"""
    records = []
    for code in codes:
        records.append({
            "code": code,
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
            **_make_scores(60, 60, 60, 60, 60),
        })
    for code in candidate_codes:
        records.append({
            "code": code,
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
            **_make_scores(70, 70, 70, 70, 70),
        })
    f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
    for record in records:
        f.write(json.dumps(record) + "\n")
    f.close()
    return f.name


class _FakePortfolioDimensions:
    """模拟 PortfolioDimensions。"""

    def __init__(self, score: float = 60.0):
        self.score = score

    def to_score_dict(self) -> dict:
        return {"fake": self.score}


def _fake_evaluate_portfolio_from_scores(_codes, _scores, _weights, _objective=None):
    """mock evaluate_portfolio_from_scores，返回固定分数和假维度对象。"""
    return 60.0, _FakePortfolioDimensions(60.0)


def _setup_mocks():
    """安装 scoring mock。"""
    engine.evaluate_portfolio_from_scores = _fake_evaluate_portfolio_from_scores
    search_module.evaluate_portfolio_from_scores = _fake_evaluate_portfolio_from_scores


def test_suggest_rebalance_basic():
    """suggest_rebalance 返回按 improvement 排序的前 top_k 方案。"""
    _setup_mocks()
    scores_path = _make_scores_path(["A", "B"], ["X"])
    try:
        plans = engine.suggest_rebalance(
            current_codes=["A", "B"],
            current_weights=[0.6, 0.4],
            scores_path=scores_path,
            max_actions=1,
            min_improvement=0.0,
            weight_strategy="proportional",
            top_k=1,
        )

        assert isinstance(plans, list)
        assert len(plans) <= 1
        for plan in plans:
            assert isinstance(plan, RebalancePlan)
            assert plan.objective == "composite_score"
            assert abs(plan.score_before - 60.0) < 1e-9
            assert abs(plan.score_after - 60.0) < 1e-9
            assert abs(plan.improvement) < 1e-9
        print("  [OK] test_suggest_rebalance_basic 通过")
    finally:
        os.unlink(scores_path)


def test_suggest_rebalance_top_k():
    """top_k 正确截断返回结果。"""
    _setup_mocks()
    scores_path = _make_scores_path(["A", "B"], ["X"])
    try:
        plans = engine.suggest_rebalance(
            current_codes=["A", "B"],
            current_weights=[0.6, 0.4],
            scores_path=scores_path,
            objective="composite_score",
            max_actions=1,
            min_improvement=0.0,
            weight_strategy="proportional",
            top_k=0,
        )

        assert len(plans) == 0
        print("  [OK] test_suggest_rebalance_top_k 通过")
    finally:
        os.unlink(scores_path)


def test_suggest_rebalance_invalid_strategy():
    """不支持的权重策略应抛出 ValueError。"""
    _setup_mocks()
    scores_path = _make_scores_path(["A", "B"], ["X"])
    try:
        try:
            engine.suggest_rebalance(
                current_codes=["A", "B"],
                current_weights=[0.6, 0.4],
                scores_path=scores_path,
                weight_strategy="unknown_strategy",
            )
            raise AssertionError("应抛出 ValueError")
        except ValueError as e:
            assert "不支持的权重策略" in str(e)
        print("  [OK] test_suggest_rebalance_invalid_strategy 通过")
    finally:
        os.unlink(scores_path)


def test_suggest_rebalance_empty_current_codes():
    """当前组合为空应抛出 ValueError。"""
    _setup_mocks()
    scores_path = _make_scores_path([], ["X"])
    try:
        try:
            engine.suggest_rebalance(
                current_codes=[],
                current_weights=[],
                scores_path=scores_path,
            )
            raise AssertionError("应抛出 ValueError")
        except ValueError as e:
            assert "当前组合不能为空" in str(e)
        print("  [OK] test_suggest_rebalance_empty_current_codes 通过")
    finally:
        os.unlink(scores_path)


def test_suggest_rebalance_weight_length_mismatch():
    """current_weights 与 current_codes 长度不一致应抛出 ValueError。"""
    _setup_mocks()
    scores_path = _make_scores_path(["A", "B"], ["X"])
    try:
        try:
            engine.suggest_rebalance(
                current_codes=["A", "B"],
                current_weights=[0.5],
                scores_path=scores_path,
            )
            raise AssertionError("应抛出 ValueError")
        except ValueError as e:
            assert "current_weights 长度必须与 current_codes 一致" in str(e)
        print("  [OK] test_suggest_rebalance_weight_length_mismatch 通过")
    finally:
        os.unlink(scores_path)

def test_suggest_rebalance_empty_candidate_pool():
    """候选股票池为空应抛出 ValueError。"""
    _setup_mocks()
    # scores_path 中只包含当前组合，排除后候选池为空
    scores_path = _make_scores_path(["A", "B"], [])

    try:
        try:
            engine.suggest_rebalance(
                current_codes=["A", "B"],
                current_weights=[0.6, 0.4],
                scores_path=scores_path,
            )
            raise AssertionError("应抛出 ValueError")
        except ValueError as e:
            assert "候选股票池不能为空" in str(e)
        print("  [OK] test_suggest_rebalance_empty_candidate_pool 通过")
    finally:
        os.unlink(scores_path)


def test_suggest_rebalance_max_actions_clamping():
    """max_actions 超过当前标点数时自动截断。"""
    _setup_mocks()
    scores_path = _make_scores_path(["A", "B"], ["X"])
    try:
        plans = engine.suggest_rebalance(
            current_codes=["A", "B"],
            current_weights=[0.6, 0.4],
            scores_path=scores_path,
            max_actions=10,
            top_k=10,
        )

        assert isinstance(plans, list)
        print("  [OK] test_suggest_rebalance_max_actions_clamping 通过")
    finally:
        os.unlink(scores_path)


def run_all_tests():
    """运行所有测试。"""
    tests = [
        ("suggest_rebalance_basic", test_suggest_rebalance_basic),
        ("suggest_rebalance_top_k", test_suggest_rebalance_top_k),
        ("suggest_rebalance_invalid_strategy", test_suggest_rebalance_invalid_strategy),
        ("suggest_rebalance_empty_current_codes", test_suggest_rebalance_empty_current_codes),
        ("suggest_rebalance_weight_length_mismatch", test_suggest_rebalance_weight_length_mismatch),
        ("suggest_rebalance_empty_candidate_pool", test_suggest_rebalance_empty_candidate_pool),
        ("suggest_rebalance_max_actions_clamping", test_suggest_rebalance_max_actions_clamping),
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
