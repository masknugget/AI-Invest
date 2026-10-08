"""
portfolio_advisor 调仓建议测试（自定义 runner 模式，非 pytest）

覆盖：rebalance 模块（loader / engine / scoring / weights / constraints）
调仓走真实 stock_dimension_scores.jsonl（本仓库自带 fixture）。

用法：
    python tests/test_recommender/test_portfolio_advisor/test_rebalance.py
"""
import json
import sys
import tempfile
import warnings
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

if sys.platform == "win32" and sys.stdout.encoding != "utf-8":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from recommender.portfolio_advisor.dimension.run import load_random_portfolio
from recommender.portfolio_advisor.rebalance import (
    CandidatePool,
    suggest_rebalance,
    suggest_rebalance_by_scores,
)
from recommender.portfolio_advisor.rebalance.constraints import clamp_max_actions
from recommender.portfolio_advisor.rebalance.loader import (
    get_current_stock_scores,
    load_candidate_pool_from_jsonl,
    load_stock_scores_from_jsonl,
)
from recommender.portfolio_advisor.rebalance.scoring import (
    evaluate_portfolio_from_scores,
    extract_objective_score,
)
from recommender.portfolio_advisor.rebalance.types import StockCandidate
from recommender.portfolio_advisor.rebalance.weights import WEIGHT_STRATEGIES, replace_stock

SCORES_PATH = str(
    project_root / "recommender" / "portfolio_advisor" / "data" / "stock_dimension_scores.jsonl"
)
DIMENSION_NAMES = (
    "drawdown_control",
    "portfolio_diversification",
    "position_efficiency",
    "return_stability",
    "style_balance",
)


def _first_codes(n: int):
    codes = []
    with open(SCORES_PATH, encoding="utf-8") as f:
        for line in f:
            codes.append(json.loads(line)["code"])
            if len(codes) >= n:
                break
    return codes


def _equal_weights(n: int):
    w = [round(1.0 / n, 4)] * n
    w[-1] = round(1.0 - sum(w[:-1]), 4)
    return w


# ============================================================================
# loader
# ============================================================================

def test_load_stock_scores():
    print("=== 测试 load_stock_scores_from_jsonl ===")
    scores = load_stock_scores_from_jsonl(SCORES_PATH)
    assert len(scores) > 0, "得分文件为空"
    for code, dims in list(scores.items())[:5]:
        assert set(dims.keys()) == set(DIMENSION_NAMES), f"{code} 维度不完整: {dims.keys()}"
    print(f"共 {len(scores)} 只股票，五维完整")
    print("✅ 通过")


def test_get_current_stock_scores():
    print("=== 测试 get_current_stock_scores 正常与缺失路径 ===")
    codes = _first_codes(3)
    scores = get_current_stock_scores(codes, SCORES_PATH)
    assert len(scores) == 3
    assert set(scores[0].keys()) == set(DIMENSION_NAMES)

    try:
        get_current_stock_scores(["sz.999999"], SCORES_PATH)
    except ValueError as e:
        print(f"  缺失代码 -> ValueError: {e}")
    else:
        raise AssertionError("缺失得分的代码应抛出 ValueError")
    print("✅ 通过")


def test_load_candidate_pool_require_code():
    print("=== 测试 load_candidate_pool require_code 行为 ===")
    # require_code=True 时缺少 code 字段应报错
    with tempfile.TemporaryDirectory() as tmp:
        bad_path = Path(tmp) / "bad.jsonl"
        bad_path.write_text('{"drawdown_control": 50}\n', encoding="utf-8")
        try:
            load_candidate_pool_from_jsonl(str(bad_path), require_code=True, fetch_full_df=False)
        except ValueError:
            print("  require_code=True -> ValueError ✅")
        else:
            raise AssertionError("缺少 code 且 require_code=True 应抛出 ValueError")

        # require_code=False 时跳过无 code 记录
        pool = load_candidate_pool_from_jsonl(
            str(bad_path), require_code=False, fetch_full_df=False
        )
        assert pool == [], f"应跳过无 code 记录，实际 {pool}"
        print("  require_code=False -> 跳过 ✅")
    print("✅ 通过")


# ============================================================================
# constraints / scoring
# ============================================================================

def test_load_code_name_tolerates_missing_name():
    print("=== 测试 load_code_name_from_jsonl 容错 ===")
    from recommender.portfolio_advisor.rebalance.loader import load_code_name_from_jsonl
    # 当前 fixture 带 name 字段：正常加载
    named = load_code_name_from_jsonl(SCORES_PATH)
    assert len(named) > 0 and named.get("sh.600000") == "浦发银行", \
        f"fixture 应包含 name，实际样例 {dict(list(named.items())[:1])}"
    # one.py 生成的得分文件不含 name 字段：旧实现 KeyError，现应跳过并返回空字典
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "no_name.jsonl"
        p.write_text(
            '{"code": "sh.600000", "drawdown_control": 50}\n'
            '{"code": "sh.600004", "name": "白云机场"}\n',
            encoding="utf-8",
        )
        mixed = load_code_name_from_jsonl(str(p))
    assert mixed == {"sh.600004": "白云机场"}, f"应跳过缺 name 的记录，实际 {mixed}"
    print(f"fixture 含 {len(named)} 个名称；无 name 记录被跳过 ✅")
    print("✅ 通过")


def test_clamp_max_actions():
    print("=== 测试 clamp_max_actions 边界 ===")
    assert clamp_max_actions(1, 5) == 1
    assert clamp_max_actions(2, 5) == 2
    assert clamp_max_actions(5, 2) == 2  # 超过组合大小，收敛
    try:
        clamp_max_actions(0, 5)
    except ValueError:
        print("  max_actions=0 -> ValueError ✅")
    else:
        raise AssertionError("max_actions < 1 应抛出 ValueError")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert clamp_max_actions(9, 5) == 3  # 超过 3，收敛到 3
    print("✅ 通过")


def test_extract_objective_score():
    print("=== 测试 extract_objective_score 各目标 ===")
    codes = _first_codes(3)
    weights = _equal_weights(3)
    scores = get_current_stock_scores(codes, SCORES_PATH)
    _, portfolio = evaluate_portfolio_from_scores(codes, scores, weights, "composite_score")

    assert extract_objective_score(portfolio, "composite_score") == portfolio.composite_score
    assert extract_objective_score(portfolio, "geometric_composite_score") == \
        portfolio.geometric_composite_score
    assert extract_objective_score(portfolio, "min_dimension_score") == \
        min(portfolio.to_score_dict().values())
    assert extract_objective_score(portfolio, "dimension:return_stability") == \
        portfolio.return_stability.score

    for bad in ("unknown_objective", "dimension:not_a_dim"):
        try:
            extract_objective_score(portfolio, bad)
        except ValueError:
            print(f"  {bad} -> ValueError ✅")
        else:
            raise AssertionError(f"非法目标 {bad} 应抛出 ValueError")
    print("✅ 通过")


# ============================================================================
# engine: suggest_rebalance
# ============================================================================

def test_suggest_rebalance_normal():
    print("=== 测试 suggest_rebalance 正常路径 ===")
    codes = _first_codes(4)
    weights = _equal_weights(4)
    plans = suggest_rebalance(codes, weights, SCORES_PATH, max_actions=1, top_k=3)
    assert isinstance(plans, list)
    print(f"方案数: {len(plans)}")
    if plans:
        plan = plans[0]
        assert plan.improvement > 0, "返回的方案应有正提升"
        assert abs(plan.score_after - plan.score_before - plan.improvement) < 1e-6
        assert len(plan.actions) >= 1
        # 方案携带调仓后权重，且归一化
        assert len(plan.weights_after) == len(codes), "weights_after 长度应等于组合标的数"
        assert abs(sum(plan.weights_after) - 1.0) < 1e-6, "weights_after 和应为 1"
        assert "weights_after" in plan.to_dict(), "to_dict 应包含 weights_after"
        print(f"首个方案提升: {plan.improvement:.2f}, 动作: {plan.actions[0].action_type}, "
              f"weights_after: {[round(w, 4) for w in plan.weights_after]}")
    print("✅ 通过")


def test_suggest_rebalance_strategies():
    print("=== 测试不同权重再分配策略 ===")
    codes = _first_codes(4)
    for strategy in WEIGHT_STRATEGIES:
        plans = suggest_rebalance(
            codes, _equal_weights(4), SCORES_PATH,
            max_actions=1, top_k=2, weight_strategy=strategy,
            fixed_new_weight=0.2 if strategy == "fixed_new_weight" else 0.0,
        )
        assert isinstance(plans, list)
        for plan in plans:
            assert plan.improvement > 0, f"{strategy} 方案提升应为正"
        print(f"  {strategy}: {len(plans)} 个方案")
    print("✅ 通过")


def test_suggest_rebalance_error_paths():
    print("=== 测试 suggest_rebalance 错误路径 ===")
    codes = _first_codes(3)
    weights = _equal_weights(3)

    cases = [
        (lambda: suggest_rebalance([], [], SCORES_PATH), "空组合"),
        (lambda: suggest_rebalance(codes, [0.5, 0.5], SCORES_PATH), "权重长度不一致"),
        (lambda: suggest_rebalance(codes, weights, SCORES_PATH,
                                   weight_strategy="no_such"), "非法权重策略"),
        (lambda: suggest_rebalance(["sz.999999"], [1.0], SCORES_PATH), "缺失维度得分"),
        (lambda: suggest_rebalance(codes, weights, SCORES_PATH, max_actions=0), "max_actions=0"),
    ]
    for fn, name in cases:
        try:
            fn()
        except ValueError as e:
            print(f"  {name}: {e}")
        else:
            raise AssertionError(f"{name} 应抛出 ValueError")
    print("✅ 通过")


def test_suggest_rebalance_by_scores():
    print("=== 测试 suggest_rebalance_by_scores（内存候选池） ===")
    codes = _first_codes(4)
    weights = _equal_weights(4)
    current_scores = get_current_stock_scores(codes, SCORES_PATH)
    all_scores = load_stock_scores_from_jsonl(SCORES_PATH)
    candidates = [
        StockCandidate(code=c, dimension_scores=d)
        for c, d in all_scores.items() if c not in set(codes)
    ]
    pool = CandidatePool(candidates=candidates)
    plans = suggest_rebalance_by_scores(
        codes, weights, current_scores, pool, max_actions=1, top_k=3
    )
    assert isinstance(plans, list)
    if plans:
        assert plans[0].improvement > 0
    print(f"方案数: {len(plans)}")
    print("✅ 通过")


# ============================================================================
# weights: replace_stock
# ============================================================================

def test_search_space_guard():
    print("=== 测试调仓搜索空间防护 ===")
    codes = _first_codes(4)
    weights = _equal_weights(4)
    # max_actions=3 + 300 只候选 ≈ 4500 万方案：应报错并给出收敛路径
    try:
        suggest_rebalance(codes, weights, SCORES_PATH, max_actions=3)
    except ValueError as e:
        assert "candidate_limit" in str(e), f"错误信息应提示 candidate_limit: {e}"
        print(f"  空间超限 -> ValueError（含收敛提示）✅")
    else:
        raise AssertionError("搜索空间超限应抛出 ValueError")
    # 缩小候选池后同参数可运行
    plans = suggest_rebalance(
        codes, weights, SCORES_PATH, max_actions=3, candidate_limit=30
    )
    assert isinstance(plans, list)
    print(f"  candidate_limit=30 后正常运行，方案数 {len(plans)} ✅")
    print("✅ 通过")


def test_synthetic_portfolio_metrics_propagation():
    print("=== 测试合成 PortfolioDimensions 的指标传播 ===")
    from recommender.portfolio_advisor.rebalance.scoring import (
        evaluate_portfolio_from_scores,
    )

    dims = {d: 60.0 for d in DIMENSION_NAMES}
    # 两只股票均携带原始指标（新版 one.py 输出格式）
    scores_with_metrics = [
        {**dims, "mdd": 0.30, "sharpe_ratio": 1.0},
        {**dims, "mdd": 0.10, "sharpe_ratio": 2.0},
    ]
    _, portfolio = evaluate_portfolio_from_scores(
        ["A", "B"], scores_with_metrics, [0.5, 0.5], "composite_score"
    )
    # 加权平均近似：mdd = (0.30+0.10)/2 = 0.20，sharpe = 1.5
    assert abs(portfolio.drawdown_control.mdd - 0.20) < 1e-9, portfolio.drawdown_control.mdd
    assert abs(portfolio.position_efficiency.sharpe_ratio - 1.5) < 1e-9
    # 未持久化的指标仍为 0（如 enb_risk_based）
    assert portfolio.portfolio_diversification.enb_risk_based == 0.0
    # 得分不受指标键影响
    assert portfolio.composite_score == 60.0

    # 旧版得分文件（无指标字段）：指标置 0，得分不受影响
    _, legacy = evaluate_portfolio_from_scores(
        ["A", "B"], [dict(dims), dict(dims)], [0.5, 0.5], "composite_score"
    )
    assert legacy.drawdown_control.mdd == 0.0
    assert legacy.composite_score == 60.0
    print(f"指标传播: mdd={portfolio.drawdown_control.mdd}, sharpe={portfolio.position_efficiency.sharpe_ratio}；"
          f"旧格式兼容 ✅")
    print("✅ 通过")


def test_replace_stock():
    print("=== 测试 replace_stock 1v1 替换 ===")
    dfs = load_random_portfolio(n_assets=3)
    codes = [str(df["code"].iloc[0]) for df in dfs]
    weights = _equal_weights(3)
    candidate = StockCandidate(
        code="sz.000001",
        dimension_scores={dim: 60.0 for dim in DIMENSION_NAMES},
    )
    new_codes, new_weights, new_dfs = replace_stock(
        codes, weights, dfs, codes[1], candidate, weight_strategy="proportional"
    )
    # 替换语义：调出码移除，剩余保持原顺序，调入码追加到末尾
    assert len(new_codes) == 3
    assert "sz.000001" in new_codes and codes[1] not in new_codes
    assert codes[0] in new_codes and codes[2] in new_codes
    assert abs(sum(new_weights) - 1.0) < 1e-6, f"替换后权重和应为 1: {new_weights}"
    assert len(new_dfs) == 3

    # 调出不在组合中的代码应报错
    try:
        replace_stock(codes, weights, dfs, "sz.404404", candidate)
    except ValueError:
        print("  调出代码不在组合中 -> ValueError ✅")
    else:
        raise AssertionError("调出代码不存在应抛出 ValueError")
    print(f"替换 {codes[1]} -> sz.000001, 权重: {[round(w, 4) for w in new_weights]}")
    print("✅ 通过")


def run_all_tests():
    tests = [
        ("load_stock_scores", test_load_stock_scores),
        ("get_current_stock_scores", test_get_current_stock_scores),
        ("candidate_require_code", test_load_candidate_pool_require_code),
        ("load_code_name", test_load_code_name_tolerates_missing_name),
        ("clamp_max_actions", test_clamp_max_actions),
        ("extract_objective_score", test_extract_objective_score),
        ("suggest_rebalance_normal", test_suggest_rebalance_normal),
        ("suggest_rebalance_strategies", test_suggest_rebalance_strategies),
        ("suggest_rebalance_errors", test_suggest_rebalance_error_paths),
        ("suggest_by_scores", test_suggest_rebalance_by_scores),
        ("search_space_guard", test_search_space_guard),
        ("synthetic_metrics", test_synthetic_portfolio_metrics_propagation),
        ("replace_stock", test_replace_stock),
    ]
    passed = failed = 0
    for name, func in tests:
        try:
            func()
            passed += 1
        except Exception as e:
            print(f"❌ {name} failed: {e}")
            failed += 1
        print("-" * 60)
    print(f"[test_rebalance] 结果: {passed} 通过, {failed} 失败")
    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if run_all_tests() else 1)
