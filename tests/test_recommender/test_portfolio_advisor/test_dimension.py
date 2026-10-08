"""
portfolio_advisor 五维诊断测试（自定义 runner 模式，非 pytest）

覆盖：dimension/run.py（组合五维）、dimension/run_one.py（单股五维）、
      几何加权综合分、资产加载边界

用法：
    python tests/test_recommender/test_portfolio_advisor/test_dimension.py
"""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

if sys.platform == "win32" and sys.stdout.encoding != "utf-8":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from recommender.portfolio_advisor.dimension.run import (
    DEFAULT_DIMENSION_WEIGHTS,
    GEOMETRIC_DIMENSION_WEIGHTS,
    compute_geometric_composite_score,
    compute_portfolio_dimensions,
    load_random_portfolio,
)
from recommender.portfolio_advisor.dimension.run_one import compute_stock_dimensions

DIMENSION_NAMES = (
    "drawdown_control",
    "portfolio_diversification",
    "position_efficiency",
    "return_stability",
    "style_balance",
)


def _check_score_range(score_dict):
    for dim, score in score_dict.items():
        assert 0.0 <= score <= 100.0, f"{dim} 得分越界: {score}"


# ============================================================================
# 权重常量
# ============================================================================

def test_default_weights_sum_to_one():
    print("=== 测试默认维度权重之和为 1 ===")
    for name, weights in (("DEFAULT", DEFAULT_DIMENSION_WEIGHTS),
                          ("GEOMETRIC", GEOMETRIC_DIMENSION_WEIGHTS)):
        total = sum(weights.values())
        assert abs(total - 1.0) < 1e-9, f"{name} 权重之和为 {total}"
        assert set(weights.keys()) == set(DIMENSION_NAMES), f"{name} 维度键不一致"
    print("✅ 通过")


# ============================================================================
# 几何加权综合分
# ============================================================================

def test_geometric_composite_basic():
    print("=== 测试几何加权综合分基本计算 ===")
    scores = {dim: 80.0 for dim in DIMENSION_NAMES}
    geo = compute_geometric_composite_score(scores, GEOMETRIC_DIMENSION_WEIGHTS)
    assert abs(geo - 80.0) < 1e-6, f"等值得分应仍为 80，实际 {geo}"

    # 低于算术平均（几何加权惩罚低分项）
    scores = {"drawdown_control": 0.0, "return_stability": 100.0,
              "position_efficiency": 100.0, "portfolio_diversification": 100.0,
              "style_balance": 100.0}
    geo = compute_geometric_composite_score(scores, GEOMETRIC_DIMENSION_WEIGHTS)
    assert geo == 0.0, "任一维度为 0 时几何加权应为 0"
    print("✅ 通过")


def test_geometric_composite_errors():
    print("=== 测试几何加权错误路径 ===")
    scores = {dim: 50.0 for dim in DIMENSION_NAMES}
    bad_weights = {"drawdown_control": 1.0, "return_stability": 1.0,
                   "position_efficiency": 1.0, "portfolio_diversification": 1.0,
                   "style_balance": 1.0}  # 和为 5
    try:
        compute_geometric_composite_score(scores, bad_weights)
    except ValueError:
        print("  权重和不为 1 -> ValueError ✅")
    else:
        raise AssertionError("权重和不为 1 应抛出 ValueError")

    # 旧实现 ±0.001 宽容带会放行的偏差，现在必须报错
    sloppy = {"drawdown_control": 0.25, "return_stability": 0.20,
              "position_efficiency": 0.25, "portfolio_diversification": 0.15,
              "style_balance": 0.1505}  # 和为 1.0005
    try:
        compute_geometric_composite_score(scores, sloppy)
    except ValueError:
        print("  权重和偏差 0.0005 -> ValueError ✅")
    else:
        raise AssertionError("权重和明显不为 1 应抛出 ValueError")

    # 浮点舍入误差（0.1+0.2+0.3+0.4=1.0000000000000002）仍可接受
    floaty = {"drawdown_control": 0.1 + 0.2, "return_stability": 0.3,
              "position_efficiency": 0.1, "portfolio_diversification": 0.1,
              "style_balance": 0.2}
    compute_geometric_composite_score(scores, floaty)
    print("  浮点舍入误差可接受 ✅")

    try:
        compute_geometric_composite_score({"drawdown_control": 50.0},
                                          GEOMETRIC_DIMENSION_WEIGHTS)
    except ValueError:
        print("  缺少维度得分 -> ValueError ✅")
    else:
        raise AssertionError("缺少维度得分应抛出 ValueError")
    print("✅ 通过")


# ============================================================================
# 组合五维诊断
# ============================================================================

def test_portfolio_dimensions_normal():
    print("=== 测试 compute_portfolio_dimensions 正常路径 ===")
    dfs = load_random_portfolio(n_assets=5)
    weights = [0.2, 0.2, 0.2, 0.2, 0.2]
    result = compute_portfolio_dimensions(dfs, weights)

    score_dict = result.to_score_dict()
    assert set(score_dict.keys()) == set(DIMENSION_NAMES)
    _check_score_range(score_dict)

    assert 0.0 <= result.composite_score <= 100.0
    assert 0.0 <= result.geometric_composite_score <= 100.0
    assert abs(sum(result.dimension_weights.values()) - 1.0) < 1e-9
    # 原始指标应为有限数值
    for value in (result.drawdown_control.mdd,
                  result.portfolio_diversification.enb_weight_based,
                  result.position_efficiency.sharpe_ratio,
                  result.return_stability.annualized_volatility,
                  result.style_balance.style_hhi):
        assert value == value and abs(value) != float("inf"), f"指标非法: {value}"

    print(f"综合健康分: {result.composite_score:.2f}, 几何加权: {result.geometric_composite_score:.2f}")
    print("✅ 通过")


def test_portfolio_dimensions_custom_weights():
    print("=== 测试自定义维度权重 ===")
    dfs = load_random_portfolio(n_assets=3)
    weights = [1 / 3, 1 / 3, 1 / 3]
    custom = {"return_stability": 1.0, "position_efficiency": 0.0,
              "style_balance": 0.0, "drawdown_control": 0.0,
              "portfolio_diversification": 0.0}
    result = compute_portfolio_dimensions(dfs, weights, dimension_weights=custom)
    assert abs(result.composite_score - result.return_stability.score) < 1e-6, \
        "权重集中到单一维度后综合分应等于该维度得分"
    print(f"综合分 == 收益稳定分: {result.composite_score:.2f}")
    print("✅ 通过")


def test_load_random_portfolio_boundary():
    print("=== 测试 load_random_portfolio 边界 ===")
    assert len(load_random_portfolio(n_assets=1)) == 1
    assert len(load_random_portfolio(n_assets=5)) == 5
    try:
        load_random_portfolio(n_assets=6)
    except ValueError:
        print("  n_assets=6 -> ValueError ✅")
    else:
        raise AssertionError("n_assets 超过可用资产数应抛出 ValueError")
    print("✅ 通过")


# ============================================================================
# 单股五维诊断
# ============================================================================

def test_stock_dimensions_normal():
    print("=== 测试 compute_stock_dimensions 正常路径 ===")
    df = load_random_portfolio(n_assets=1)[0]
    result = compute_stock_dimensions(df)
    _check_score_range(result.to_score_dict())
    # 单股风格均衡固定为中性 50 分
    assert result.style_balance.score == 50.0
    assert result.style_balance.style_hhi == 1.0
    print(f"{df['code'].iloc[0]} 综合健康分: {result.composite_score:.2f}")
    print("✅ 通过")


def test_stock_dimensions_type_error():
    print("=== 测试 compute_stock_dimensions 类型校验 ===")
    try:
        # 故意传入错误类型，验证运行时类型校验（type: ignore 仅为通过静态检查）
        compute_stock_dimensions([load_random_portfolio(n_assets=1)[0]])  # type: ignore[arg-type]
    except TypeError:
        print("✅ 通过（非 DataFrame 抛出 TypeError）")
    else:
        raise AssertionError("传入列表应抛出 TypeError")


def test_enb_semantics():
    print("=== 测试有效下注数（ENB）语义 ===")
    from recommender.portfolio_advisor.dimension.portfolio_diversification import (
        effective_number_of_bets_risk_based,
        effective_number_of_bets_weight_based,
        normalize_enb_to_score,
    )
    # 等权 2 资产 -> ENB=2（最分散）；单资产 -> ENB=1（最集中）
    assert effective_number_of_bets_weight_based([0.5, 0.5]) == 2.0
    assert effective_number_of_bets_weight_based([1.0]) == 1.0
    assert normalize_enb_to_score(2.0, 2) == 100.0
    assert normalize_enb_to_score(1.0, 2) == 50.0
    # 非法输入
    try:
        effective_number_of_bets_weight_based([0.5, 0.6])  # 和不为 1
    except ValueError:
        print("  权重和不为 1 -> ValueError ✅")
    else:
        raise AssertionError("权重和不为 1 应抛出 ValueError")
    try:
        effective_number_of_bets_weight_based([1.0, -0.0 - 0.1])  # 负数
    except ValueError:
        print("  负权重 -> ValueError ✅")
    else:
        raise AssertionError("负权重应抛出 ValueError")
    # 协方差矩阵形状不匹配
    import numpy as np
    try:
        effective_number_of_bets_risk_based([0.5, 0.5], np.array([[1.0]]))
    except ValueError:
        print("  协方差矩阵形状不匹配 -> ValueError ✅")
    else:
        raise AssertionError("协方差矩阵形状不匹配应抛出 ValueError")
    print("✅ 通过")


def test_sharpe_nan_and_insufficient_data():
    print("=== 测试夏普比率 NaN 防护与数据不足 ===")
    import numpy as np
    import pandas as pd
    from recommender.portfolio_advisor.dimension.position_efficiency import (
        calculate_portfolio_sharpe_ratio,
        normalize_sharpe_to_score,
    )

    # NaN / 负值输入不得误判为满分
    assert normalize_sharpe_to_score(float("nan")) == 0.0, "NaN 应得 0 分而非满分"
    assert normalize_sharpe_to_score(-1.5) == 0.0
    assert normalize_sharpe_to_score(1.5) == 75.0

    # 两个资产仅 1 个共同交易日 -> 应抛 ValueError 而不是产出 NaN
    df_a = pd.DataFrame({"date": ["2024-01-02", "2024-01-03"], "pctChg": [1.0, 2.0]})
    df_b = pd.DataFrame({"date": ["2024-01-01", "2024-01-02"], "pctChg": [0.5, 1.0]})
    try:
        calculate_portfolio_sharpe_ratio([df_a, df_b], [0.5, 0.5])
    except ValueError as e:
        print(f"  共同交易日不足 -> ValueError: {e}")
    else:
        raise AssertionError("对齐后不足 2 天应抛出 ValueError")
    print("✅ 通过")


def test_duplicate_dates_consistent_across_dimensions():
    print("=== 测试含重复日期时各维度口径一致 ===")
    from recommender.portfolio_advisor.data_read import df_1, df_2
    from recommender.portfolio_advisor.dimension.portfolio_diversification import (
        compute_enb_from_dataframes,
    )
    from recommender.portfolio_advisor.dimension.run import compute_drawdown_control

    assert df_1["date"].duplicated().any(), "fixture 应包含重复日期以验证此场景"

    def dedup(df):
        return df.drop_duplicates(subset="date", keep="last").reset_index(drop=True)

    dfs_raw = [df_1, df_2]
    dfs_clean = [dedup(df_1), dedup(df_2)]

    # 回撤维度：原始（含重复日期）与预去重结果应一致（模块内部去重）
    mdd_raw = compute_drawdown_control(dfs_raw, [0.5, 0.5])
    mdd_clean = compute_drawdown_control(dfs_clean, [0.5, 0.5])
    assert abs(mdd_raw.mdd - mdd_clean.mdd) < 1e-12, \
        f"回撤维度重复日期口径不一致: {mdd_raw.mdd} vs {mdd_clean.mdd}"

    # 分散度维度：协方差矩阵不受重复日期污染
    enb_raw = compute_enb_from_dataframes(dfs_raw, [0.5, 0.5])
    enb_clean = compute_enb_from_dataframes(dfs_clean, [0.5, 0.5])
    assert abs(enb_raw["enb_risk_based"] - enb_clean["enb_risk_based"]) < 1e-12, \
        f"ENB 口径不一致: {enb_raw['enb_risk_based']} vs {enb_clean['enb_risk_based']}"
    print(f"MDD={mdd_raw.mdd:.4f}（口径一致）, ENB(risk)={enb_raw['enb_risk_based']:.4f}（口径一致）")
    print("✅ 通过")


def test_pctchg_scale_adaptive():
    print("=== 测试 pctChg 百分比/小数两种量纲结果一致 ===")
    import pandas as pd
    from recommender.portfolio_advisor.dimension.position_efficiency import (
        calculate_portfolio_sharpe_ratio,
    )

    dates = pd.date_range("2024-01-01", periods=60, freq="D").strftime("%Y-%m-%d")
    # 注意：量纲自适应依赖 max|pctChg| > 1 判断，若某日涨跌幅 >= 1%
    # （百分比值 > 1）即可无歧义区分两种量纲；全部 < 1% 的数据在
    # 理论上不可区分（return_stability 存在同样限制）。
    decimal_returns = [0.005, -0.003, 0.015, -0.001] * 15      # 小数制
    percent_returns = [r * 100 for r in decimal_returns]       # 百分比制
    df_decimal = pd.DataFrame({"date": dates, "pctChg": decimal_returns})
    df_percent = pd.DataFrame({"date": dates, "pctChg": percent_returns})

    sharpe_decimal = calculate_portfolio_sharpe_ratio([df_decimal], [1.0])
    sharpe_percent = calculate_portfolio_sharpe_ratio([df_percent], [1.0])
    assert abs(sharpe_decimal - sharpe_percent) < 1e-9, \
        f"两种量纲的夏普应一致: {sharpe_decimal} vs {sharpe_percent}"
    print(f"decimal 与 percent 量纲夏普一致: {sharpe_decimal:.4f}")
    print("✅ 通过")


def run_all_tests():
    tests = [
        ("default_weights", test_default_weights_sum_to_one),
        ("geometric_basic", test_geometric_composite_basic),
        ("geometric_errors", test_geometric_composite_errors),
        ("enb_semantics", test_enb_semantics),
        ("sharpe_nan_guard", test_sharpe_nan_and_insufficient_data),
        ("duplicate_dates", test_duplicate_dates_consistent_across_dimensions),
        ("pctchg_scale", test_pctchg_scale_adaptive),
        ("portfolio_dimensions", test_portfolio_dimensions_normal),
        ("portfolio_custom_weights", test_portfolio_dimensions_custom_weights),
        ("load_portfolio_boundary", test_load_random_portfolio_boundary),
        ("stock_dimensions", test_stock_dimensions_normal),
        ("stock_type_error", test_stock_dimensions_type_error),
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
    print(f"[test_dimension] 结果: {passed} 通过, {failed} 失败")
    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if run_all_tests() else 1)
