"""
目标函数评分测试（普通 Python 脚本，无需 pytest）。

覆盖 recommender.portfolio_advisor.rebalance.scoring 中的核心函数：
1. extract_objective_score：从 PortfolioDimensions 中提取指定目标得分。
2. evaluate_portfolio：计算指定目标函数下的组合得分与完整诊断结果。

运行方式：
    python recommender/portfolio_advisor/test/test_rebalance/t_scoring.py
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
_module_path = os.path.join(_project_root, "recommender", "portfolio_advisor", "rebalance", "scoring.py")
_spec = importlib.util.spec_from_file_location("rebalance_scoring", _module_path)
assert _spec is not None and _spec.loader is not None, f"无法加载模块: {_module_path}"
scoring = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scoring)

OBJECTIVES = scoring.OBJECTIVES
evaluate_portfolio = scoring.evaluate_portfolio
extract_objective_score = scoring.extract_objective_score


class _FakeDimension:
    """模拟单个维度结果。"""

    def __init__(self, score: float):
        self.score = score


class _FakePortfolioDimensions:
    """模拟 PortfolioDimensions，仅提供 scoring.py 需要的属性。"""

    def __init__(self):
        self.composite_score = 80.0
        self.geometric_composite_score = 75.0
        self.drawdown_control = _FakeDimension(70.0)
        self.portfolio_diversification = _FakeDimension(80.0)
        self.position_efficiency = _FakeDimension(60.0)
        self.return_stability = _FakeDimension(90.0)
        self.style_balance = _FakeDimension(50.0)

    def to_score_dict(self) -> dict:
        return {
            "drawdown_control": self.drawdown_control.score,
            "portfolio_diversification": self.portfolio_diversification.score,
            "position_efficiency": self.position_efficiency.score,
            "return_stability": self.return_stability.score,
            "style_balance": self.style_balance.score,
        }


def _make_fake_dims():
    """构造一个 FakePortfolioDimensions 实例。"""
    return _FakePortfolioDimensions()


def test_objectives_constant():
    """OBJECTIVES 集合包含预期目标。"""
    assert "composite_score" in OBJECTIVES
    assert "geometric_composite_score" in OBJECTIVES
    assert "min_dimension_score" in OBJECTIVES
    print("  [OK] test_objectives_constant 通过")


def test_extract_composite_score():
    """extract_objective_score 正确返回综合得分。"""
    dims = _make_fake_dims()
    score = extract_objective_score(dims, "composite_score")
    assert abs(score - dims.composite_score) < 1e-9
    print("  [OK] test_extract_composite_score 通过")


def test_extract_geometric_composite_score():
    """extract_objective_score 正确返回几何加权综合得分。"""
    dims = _make_fake_dims()
    score = extract_objective_score(dims, "geometric_composite_score")
    assert abs(score - dims.geometric_composite_score) < 1e-9
    print("  [OK] test_extract_geometric_composite_score 通过")


def test_extract_min_dimension_score():
    """extract_objective_score 正确返回最低维度得分。"""
    dims = _make_fake_dims()
    score = extract_objective_score(dims, "min_dimension_score")
    expected = min(dims.to_score_dict().values())
    assert abs(score - expected) < 1e-9
    print("  [OK] test_extract_min_dimension_score 通过")


def test_extract_dimension_score():
    """extract_objective_score 支持 dimension:<name> 形式。"""
    dims = _make_fake_dims()

    score = extract_objective_score(dims, "dimension:drawdown_control")
    assert abs(score - dims.drawdown_control.score) < 1e-9

    score = extract_objective_score(dims, "dimension:return_stability")
    assert abs(score - dims.return_stability.score) < 1e-9
    print("  [OK] test_extract_dimension_score 通过")


def test_extract_objective_score_unknown_objective():
    """未知优化目标应抛出 ValueError。"""
    dims = _make_fake_dims()

    try:
        extract_objective_score(dims, "unknown_objective")
        raise AssertionError("应抛出 ValueError")
    except ValueError as e:
        assert "未知优化目标" in str(e)
    print("  [OK] test_extract_objective_score_unknown_objective 通过")


def test_extract_objective_score_unknown_dimension():
    """未知维度应抛出 ValueError。"""
    dims = _make_fake_dims()

    try:
        extract_objective_score(dims, "dimension:not_exist")
        raise AssertionError("应抛出 ValueError")
    except ValueError as e:
        assert "未知维度" in str(e)
    print("  [OK] test_extract_objective_score_unknown_dimension 通过")


def test_evaluate_portfolio_default():
    """evaluate_portfolio 默认返回 geometric_composite_score。"""
    dims = _make_fake_dims()
    setattr(scoring, "compute_portfolio_dimensions", lambda _dfs, _weights: dims)

    score, result = evaluate_portfolio(["A", "B"], [0.5, 0.5], [])
    expected = extract_objective_score(dims, "geometric_composite_score")
    assert abs(score - expected) < 1e-9
    assert result is dims
    print("  [OK] test_evaluate_portfolio_default 通过")


def test_evaluate_portfolio_composite():
    """evaluate_portfolio 指定 composite_score 目标。"""
    dims = _make_fake_dims()
    setattr(scoring, "compute_portfolio_dimensions", lambda _dfs, _weights: dims)

    score, result = evaluate_portfolio(["A", "B"], [0.5, 0.5], [], objective="composite_score")
    expected = extract_objective_score(dims, "composite_score")
    assert abs(score - expected) < 1e-9
    assert result is dims
    print("  [OK] test_evaluate_portfolio_composite 通过")


def test_evaluate_portfolio_dimension():
    """evaluate_portfolio 指定 dimension 目标。"""
    dims = _make_fake_dims()
    setattr(scoring, "compute_portfolio_dimensions", lambda _dfs, _weights: dims)

    score, result = evaluate_portfolio(
        ["A", "B"], [0.5, 0.5], [], objective="dimension:portfolio_diversification"
    )
    expected = extract_objective_score(dims, "dimension:portfolio_diversification")
    assert abs(score - expected) < 1e-9
    assert result is dims
    print("  [OK] test_evaluate_portfolio_dimension 通过")


def run_all_tests():
    """运行所有测试。"""
    tests = [
        ("objectives_constant", test_objectives_constant),
        ("extract_composite_score", test_extract_composite_score),
        ("extract_geometric_composite_score", test_extract_geometric_composite_score),
        ("extract_min_dimension_score", test_extract_min_dimension_score),
        ("extract_dimension_score", test_extract_dimension_score),
        ("extract_objective_score_unknown_objective", test_extract_objective_score_unknown_objective),
        ("extract_objective_score_unknown_dimension", test_extract_objective_score_unknown_dimension),
        ("evaluate_portfolio_default", test_evaluate_portfolio_default),
        ("evaluate_portfolio_composite", test_evaluate_portfolio_composite),
        ("evaluate_portfolio_dimension", test_evaluate_portfolio_dimension),
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
