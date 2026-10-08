"""
portfolio_advisor 压力测试模块测试（自定义 runner 模式，非 pytest）

覆盖：stress_portfolio（历史 / 宏观情景 / 板块压力）+ const 场景工具
行情数据用 fixture parquet（recommender/portfolio_advisor/data/df_*.parquet）。

用法：
    python tests/test_recommender/test_portfolio_advisor/test_stress.py
"""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

if sys.platform == "win32" and sys.stdout.encoding != "utf-8":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from recommender.portfolio_advisor.data_read import load_all
from recommender.portfolio_advisor.stress_portfolio.const import (
    build_scenarios,
    list_available_scenarios,
    make_sector_scenario,
)
from recommender.portfolio_advisor.stress_portfolio.history_stress import (
    compute_historical_stress,
    list_historical_scenario_names,
    simulate_portfolio_drawdown,
)
from recommender.portfolio_advisor.stress_portfolio.scenario_stress import (
    compute_scenario_stress,
    list_scenario_names,
)
from recommender.portfolio_advisor.stress_portfolio.sector_stress import (
    compute_sector_stress,
    list_sector_names,
)

# fixture 组合：data/df_1 ~ df_5，等权
_FIXTURE_DFS = load_all()
CODES = [str(df["code"].iloc[0]) for df in _FIXTURE_DFS.values()]
DFS_MAP = dict(zip(CODES, _FIXTURE_DFS.values()))
PORTFOLIO = [{"code": c, "weight": 0.2} for c in CODES]

# 固定行业查询：计算机/电子 -> 科技，汽车 -> 周期，医药生物 -> 医药
_INDUSTRY = {
    "sz.300005": "计算机",
    "sz.300291": "计算机",
    "sh.601689": "汽车",
    "sz.300237": "医药生物",
    "sz.300121": "电子",
}
INDUSTRY_LOOKUP = lambda code: _INDUSTRY.get(code)  # noqa: E731


# ============================================================================
# const 场景工具
# ============================================================================

def test_const_scenarios():
    print("=== 测试 const 场景列表与构造 ===")
    available = list_available_scenarios()
    assert len(available) > 0
    for item in available:
        for key in ("id", "name", "type", "params"):
            assert key in item, f"场景缺少字段 {key}"

    # 默认构建全部；按 id 选择子集
    all_scenarios = build_scenarios()
    assert len(all_scenarios) == len(available)
    first_id = available[0]["id"]
    subset = build_scenarios([first_id])
    assert len(subset) == 1 and subset[0].id == first_id

    sector_scenario = make_sector_scenario("科技", callback_pct=0.2)
    assert sector_scenario.type == "sector"
    print(f"可用场景 {len(available)} 个（历史 + 板块），按 id 选择 ✅")
    print("✅ 通过")


# ============================================================================
# 历史压力测试
# ============================================================================

def test_historical_stress_normal():
    print("=== 测试 compute_historical_stress 正常路径 ===")
    names = list_historical_scenario_names()
    assert len(names) > 0
    results = compute_historical_stress(PORTFOLIO, DFS_MAP)
    assert len(results) == len(names), f"应覆盖全部 {len(names)} 个历史场景"
    for r in results:
        for key in ("scenario_id", "scenario_name", "portfolio_loss_pct", "per_asset"):
            assert key in r, f"结果缺少字段 {key}"
        assert isinstance(r["per_asset"], list) and len(r["per_asset"]) == len(PORTFOLIO)
    print(f"场景: {[r['scenario_name'] for r in results]}")
    print(f"组合损失: {[r['portfolio_loss_pct'] for r in results]}%")
    print("✅ 通过")


def test_historical_stress_subset():
    print("=== 测试按 id 选择历史场景子集 ===")
    available = list_available_scenarios()
    hist_ids = [s["id"] for s in available if s["type"] == "historical"]
    results = compute_historical_stress(PORTFOLIO, DFS_MAP, scenario_ids=[hist_ids[0]])
    assert len(results) == 1 and results[0]["scenario_id"] == hist_ids[0]
    print(f"选中场景: {results[0]['scenario_name']}")
    print("✅ 通过")


def test_historical_stress_errors():
    print("=== 测试历史压力错误路径 ===")
    cases = [
        ([], "空持仓"),
        ([{"code": CODES[0], "weight": 0.5}], "权重和不为 1"),
        ([{"weight": 0.2} for _ in CODES], "缺少 code 字段"),
    ]
    for portfolio, name in cases:
        try:
            compute_historical_stress(portfolio, DFS_MAP)
        except ValueError as e:
            print(f"  {name}: {e}")
        else:
            raise AssertionError(f"{name} 应抛出 ValueError")
    print("✅ 通过")


def test_historical_stress_data_coverage():
    print("=== 测试历史压力数据覆盖度字段 ===")
    # 5 只持仓中 1 只无行情 -> data_coverage = 0.8，且 warnings 提示缺数据
    partial_map = dict(DFS_MAP)
    partial_map.pop(CODES[-1])
    results = compute_historical_stress(PORTFOLIO, partial_map)
    assert len(results) > 0
    for r in results:
        assert "data_coverage" in r, "结果应包含 data_coverage 字段"
        assert abs(r["data_coverage"] - 0.8) < 1e-6, f"覆盖度应为 0.8，实际 {r['data_coverage']}"
        assert any(CODES[-1] in w for w in r["warnings"]), "应有缺数据警告"
    # 全量数据 -> 覆盖度 1.0
    full = compute_historical_stress(PORTFOLIO, DFS_MAP)
    assert all(r["data_coverage"] == 1.0 for r in full), "全量数据覆盖度应为 1.0"
    print(f"缺 1 只时 coverage={results[0]['data_coverage']}，全量时 coverage=1.0")
    print("✅ 通过")


def test_simulate_portfolio_drawdown():
    print("=== 测试 simulate_portfolio_drawdown ===")
    dfs = list(_FIXTURE_DFS.values())[:3]
    result = simulate_portfolio_drawdown(dfs, [1 / 3, 1 / 3, 1 / 3], price_col="close")
    assert len(result) > 0
    for col in ("date", "portfolio_value", "drawdown"):
        assert col in result.columns, f"缺少列 {col}"
    # 累计净值应从 1 开始
    assert abs(float(result.iloc[0]["portfolio_value"]) - 1.0) < 1e-6, "初始净值应为 1"
    print(f"模拟 {len(result)} 个交易日，期末净值: {float(result.iloc[-1]['portfolio_value']):.4f}")
    print("✅ 通过")


# ============================================================================
# 宏观情景压力测试
# ============================================================================

def test_scenario_stress_normal():
    print("=== 测试 compute_scenario_stress 正常路径 ===")
    names = list_scenario_names()
    assert len(names) > 0
    # 美联储加息：科技 -15%，组合中计算机/电子（科技）占 60%，应产生明显亏损
    result = compute_scenario_stress(PORTFOLIO, "美联储加息", industry_lookup=INDUSTRY_LOOKUP)
    for key in ("scenario_name", "portfolio_loss_pct", "affected_stocks", "warnings"):
        assert key in result, f"结果缺少字段 {key}"
    # 损失为负数（-12.0 表示亏损 12%）：加息情景下科技重仓组合应产生亏损
    assert result["portfolio_loss_pct"] < 0, f"应有亏损，实际 {result['portfolio_loss_pct']}"
    assert len(result["affected_stocks"]) >= 2
    print(f"情景 {result['scenario_name']}: 损失 {result['portfolio_loss_pct']}%, "
          f"受影响 {len(result['affected_stocks'])} 只")
    print("✅ 通过")


def test_scenario_stress_unknown():
    print("=== 测试未知宏观情景 ===")
    try:
        compute_scenario_stress(PORTFOLIO, "不存在的场景", industry_lookup=INDUSTRY_LOOKUP)
    except ValueError as e:
        print(f"✅ 通过（抛出 ValueError: {e}）")
    else:
        raise AssertionError("未知情景应抛出 ValueError")


# ============================================================================
# 板块压力测试
# ============================================================================

def test_sector_stress_normal():
    print("=== 测试 compute_sector_stress 正常路径 ===")
    sectors = list_sector_names()
    assert len(sectors) > 0
    # 科技板块回调 20%：3 只科技成分股（计算机x2 + 电子x1，共 60% 权重）应受影响
    result = compute_sector_stress(
        PORTFOLIO, sector="科技", sector_callback_pct=0.20,
        industry_lookup=INDUSTRY_LOOKUP,
    )
    for key in ("sector", "portfolio_loss_pct", "per_asset", "affected_stocks"):
        assert key in result, f"结果缺少字段 {key}"
    assert result["sector"] == "科技"
    assert result["portfolio_loss_pct"] < 0, f"科技回调应产生亏损，实际 {result['portfolio_loss_pct']}"
    assert set(result["affected_stocks"]) == {"sz.300005", "sz.300291", "sz.300121"}
    print(f"科技回调 20% -> 组合损失 {result['portfolio_loss_pct']}%")
    print("✅ 通过")


def test_sector_stress_unaffected():
    print("=== 测试不受影响板块 ===")
    # 金融板块回调：组合无金融股，损失应为 0
    result = compute_sector_stress(
        PORTFOLIO, sector="金融", sector_callback_pct=0.20,
        industry_lookup=INDUSTRY_LOOKUP,
    )
    assert result["portfolio_loss_pct"] == 0, "无金融持仓时损失应为 0"
    assert result["affected_stocks"] == []
    print("✅ 通过")


def test_industry_lookup_required():
    print("=== 测试 industry_lookup 必传校验 ===")
    from recommender.portfolio_advisor.stress_portfolio.scenario_stress import (
        calculate_scenario_stress_result,
    )
    from recommender.portfolio_advisor.stress_portfolio.sector_stress import (
        calculate_sector_stress_result,
    )
    import pandas as pd

    portfolio_df = pd.DataFrame([{"code": "sh.600000", "weight": 1.0, "amount": 1.0}])
    # 不传 industry_lookup：旧实现静默降级为 mock（且 mock 代码无前缀永远不匹配），
    # 现在必须显式报错
    try:
        calculate_scenario_stress_result(portfolio_df, {"科技": -0.15})
    except ValueError as e:
        print(f"  scenario: {e}")
    else:
        raise AssertionError("scenario_stress 缺 industry_lookup 应抛出 ValueError")
    try:
        calculate_sector_stress_result(portfolio_df)
    except ValueError as e:
        print(f"  sector: {e}")
    else:
        raise AssertionError("sector_stress 缺 industry_lookup 应抛出 ValueError")
    print("✅ 通过")


def test_scenario_sector_portfolio_validation():
    print("=== 测试 scenario/sector stress 持仓校验 ===")
    bad_portfolios = [
        ([], "空持仓"),
        ([{"code": "A", "weight": 0.5}, {"code": "B", "weight": 0.3}], "权重和不为 1"),
        ([{"weight": 0.5}, {"code": "B", "weight": 0.5}], "缺少 code 字段"),
    ]
    for portfolio, name in bad_portfolios:
        for fn, label in (
            (lambda: compute_scenario_stress(portfolio, "美联储加息",
                                             industry_lookup=INDUSTRY_LOOKUP), "scenario"),
            (lambda: compute_sector_stress(portfolio, sector="科技",
                                           industry_lookup=INDUSTRY_LOOKUP), "sector"),
        ):
            try:
                fn()
            except ValueError as e:
                print(f"  {label} {name}: {str(e)[:40]}")
            else:
                raise AssertionError(f"{label} {name} 应抛出 ValueError")
    print("✅ 通过")


def run_all_tests():
    tests = [
        ("const_scenarios", test_const_scenarios),
        ("industry_lookup_required", test_industry_lookup_required),
        ("portfolio_validation", test_scenario_sector_portfolio_validation),
        ("historical_stress", test_historical_stress_normal),
        ("historical_stress_subset", test_historical_stress_subset),
        ("historical_stress_errors", test_historical_stress_errors),
        ("historical_data_coverage", test_historical_stress_data_coverage),
        ("simulate_drawdown", test_simulate_portfolio_drawdown),
        ("scenario_stress", test_scenario_stress_normal),
        ("scenario_stress_unknown", test_scenario_stress_unknown),
        ("sector_stress", test_sector_stress_normal),
        ("sector_stress_unaffected", test_sector_stress_unaffected),
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
    print(f"[test_stress] 结果: {passed} 通过, {failed} 失败")
    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if run_all_tests() else 1)
