"""
压力测试统一入口 compute_stress_test 的使用示例与基础校验。

运行方式：
    python research/portfolio_advisor/test/t_compute_stress.py

需要在项目根目录下执行，或保证 sys.path 包含项目根目录。
"""

import math
from typing import Any, Dict, List, Optional

import pandas as pd

from research.portfolio_advisor.stress_portfolio.const import (
    DEFAULT_SECTOR_CALLBACK_PCT,
    SECTOR_BETAS,
    build_scenarios,
    make_sector_scenario,
)
from research.portfolio_advisor.stress_portfolio.history_stress import (
    _load_single_df,
)
from research.portfolio_advisor.stress_portfolio.stress_test import (
    compute_stress_test,
    normalize_loss_to_score,
    risk_level,
    _ensure_portfolio_df,
)


def _fmt(value: Any) -> str:
    """格式化浮点数输出，兼容 nan / inf。"""
    if value is None:
        return "None"
    if isinstance(value, float) and math.isnan(value):
        return "nan"
    if isinstance(value, float) and math.isinf(value):
        return str(value)
    if isinstance(value, (int, float)):
        return f"{value:.4f}"
    return str(value)


def _assert_close(actual: float, expected: float, tol: float = 1e-9) -> None:
    """断言两个浮点数在容差范围内相等。"""
    assert abs(float(actual) - float(expected)) < tol, f"期望值 {expected}，实际值 {actual}"


# -----------------------------------------------------------------------------
# 测试数据构造
# -----------------------------------------------------------------------------
def _make_historical_df(
    code: str,
    start: str,
    peak_price: float,
    trough_price: float,
    n_days: int = 260,
) -> pd.DataFrame:
    """
    构造一只股票的日频行情：前半段上涨到 peak_price，后半段下跌到 trough_price。
    用于在指定历史压力场景区间内产生一个已知的最大回撤。
    """
    dates = pd.date_range(start=start, periods=n_days, freq="B").strftime("%Y-%m-%d")
    n_up = n_days // 2
    n_down = n_days - n_up

    up_prices = [peak_price / n_up * (i + 1) for i in range(n_up)]
    down_prices = [
        peak_price + (trough_price - peak_price) / n_down * (i + 1)
        for i in range(n_down)
    ]
    prices = up_prices + down_prices

    return pd.DataFrame({
        "date": dates,
        "code": code,
        "close": prices,
    })


def _make_tech_bank_portfolio() -> List[Dict[str, Any]]:
    """构造一个含科技/金融各一只标的的等权组合。"""
    return [
        {"code": "TECH1", "weight": 0.4, "amount": 40000.0},
        {"code": "BANK1", "weight": 0.6, "amount": 60000.0},
    ]


def _industry_lookup(code: str) -> Optional[str]:
    """测试用的行业查询 stub。"""
    mapping = {
        "TECH1": "电子",
        "BANK1": "银行",
    }
    return mapping.get(code)


# -----------------------------------------------------------------------------
# 1. 归一化与风险等级
# -----------------------------------------------------------------------------
print("=" * 70)
print("1. 损失百分比 -> 0-100 风险分映射")
print("=" * 70)
loss_score_cases = [
    (0.0, 0.0),
    (-10.0, 20.0),
    (-20.0, 50.0),
    (-35.0, 80.0),
    (-50.0, 100.0),
    (-60.0, 100.0),   # 超出上界截断
]
for loss, expected in loss_score_cases:
    score = normalize_loss_to_score(loss)
    _assert_close(score, expected, tol=1e-6)
    print(f"  loss={loss:>6.2f}% -> score={score:>6.2f}")

print("=" * 70)
print("2. 损失百分比 -> 风险等级")
print("=" * 70)
risk_level_cases = [
    (-5.0, "low"),
    (-15.0, "medium"),
    (-27.0, "high"),
    (-40.0, "severe"),
]
for loss, expected_level in risk_level_cases:
    level = risk_level(loss)
    assert level["level"] == expected_level, f"期望 {expected_level}，实际 {level}"
    print(f"  loss={loss:>6.2f}% -> {level}")


# -----------------------------------------------------------------------------
# 3. 场景工厂函数
# -----------------------------------------------------------------------------
print("=" * 70)
print("3. 场景工厂函数")
print("=" * 70)

all_scenarios = build_scenarios(None)
assert len(all_scenarios) >= 3, "应至少包含历史场景与板块场景"
print(f"  默认场景数量: {len(all_scenarios)}")

selected = build_scenarios(["2008年金融危机"])
assert len(selected) == 1 and selected[0].id == "2008年金融危机"
print("  build_scenarios 按 id 筛选正确")

sector_scenario = make_sector_scenario("医药", callback_pct=0.15)
assert sector_scenario.type == "sector"
assert sector_scenario.params["sector"] == "医药"
assert sector_scenario.params["callback_pct"] == 0.15
print(f"  动态板块场景: {sector_scenario.name}")

try:
    make_sector_scenario("未知板块")
    assert False, "未知板块应抛出 ValueError"
except ValueError:
    print("  未知板块正确抛出 ValueError")


# -----------------------------------------------------------------------------
# 4. 内部辅助函数
# -----------------------------------------------------------------------------
print("=" * 70)
print("4. 内部辅助函数")
print("=" * 70)

# _load_single_df 支持大小写与交易所前缀差异
sample_df = pd.DataFrame({"date": ["2020-01-01"], "code": ["sh.000001"], "close": [100.0]})
dfs_map = {"SH.000001": sample_df}
assert _load_single_df("sh.000001", dfs_map) is sample_df
assert _load_single_df("000001", dfs_map) is sample_df
print("  _load_single_df 兼容前缀/大小写")

# _ensure_portfolio_df 校验
try:
    _ensure_portfolio_df([])
    assert False, "空持仓应抛出 ValueError"
except ValueError:
    print("  空持仓正确抛出 ValueError")

try:
    _ensure_portfolio_df([{"code": "A"}])
    assert False, "缺少 weight 应抛出 ValueError"
except ValueError:
    print("  缺少 weight 正确抛出 ValueError")

try:
    _ensure_portfolio_df([{"code": "A", "weight": 0.5}, {"code": "B", "weight": 0.6}])
    assert False, "权重之和不等于 1 应抛出 ValueError"
except ValueError:
    print("  权重和校验正确抛出 ValueError")


df_portfolio = _ensure_portfolio_df([{"code": "A", "weight": 0.5}, {"code": "B", "weight": 0.5}])
assert "amount" in df_portfolio.columns
_assert_close(df_portfolio["amount"].sum(), 1.0)
print("  _ensure_portfolio_df 自动生成 amount 列")


# -----------------------------------------------------------------------------
# 5. 历史极端事件场景
# -----------------------------------------------------------------------------
print("=" * 70)
print("5. 历史极端事件场景")
print("=" * 70)

portfolio = [{"code": "STRESS", "weight": 1.0, "amount": 100000.0}]
# 构造一段行情：从 100 涨到 120 再跌到 80，最大回撤 -33.33%
df = _make_historical_df("STRESS", "2007-10-01", peak_price=120.0, trough_price=80.0, n_days=260)
dfs_map = {"STRESS": df}

result = compute_stress_test(
    portfolio,
    dfs_map=dfs_map,
    scenario_ids=["2008年金融危机"],
)
assert len(result.scenarios) == 1
scenario = result.scenarios[0]
_assert_close(scenario.portfolio_loss_pct, -33.3, tol=0.1)
_assert_close(result.total_loss_pct, -33.3, tol=0.1)
assert scenario.per_asset[0]["code"] == "STRESS"
print(f"  单票历史场景损失: {scenario.portfolio_loss_pct:.2f}%")
print(f"  组合损失金额    : {_fmt(scenario.portfolio_loss_amount)}")
print(f"  风险等级        : {result.risk_level}")
print(f"  风险分          : {_fmt(result.risk_score)}")


# -----------------------------------------------------------------------------
# 6. 板块压力场景
# -----------------------------------------------------------------------------
print("=" * 70)
print("6. 板块压力场景")
print("=" * 70)

portfolio = _make_tech_bank_portfolio()
result = compute_stress_test(
    portfolio,
    dfs_map={},
    scenario_ids=["科技板块回调20%"],
    industry_lookup=_industry_lookup,
)
assert len(result.scenarios) == 1
scenario = result.scenarios[0]
# 电子属于科技，beta=1.15，回调 20%：0.4 * (-0.20 * 1.15) = -0.092
expected_loss_pct = -0.4 * DEFAULT_SECTOR_CALLBACK_PCT * SECTOR_BETAS["科技"] * 100
_assert_close(scenario.portfolio_loss_pct, expected_loss_pct, tol=1e-6)
_assert_close(result.total_loss_pct, expected_loss_pct, tol=1e-6)
print(f"  板块场景损失: {scenario.portfolio_loss_pct:.2f}%")
print(f"  组合损失金额: {_fmt(scenario.portfolio_loss_amount)}")


# -----------------------------------------------------------------------------
# 7. 缺失行情数据的 warning
# -----------------------------------------------------------------------------
print("=" * 70)
print("7. 缺失行情数据时的降级处理")
print("=" * 70)

portfolio = [{"code": "NO_DATA", "weight": 1.0, "amount": 100000.0}]
result = compute_stress_test(
    portfolio,
    dfs_map={},
    scenario_ids=["2008年金融危机"],
)
assert len(result.warnings) == 1
assert result.scenarios[0].portfolio_loss_pct == 0.0
assert result.total_loss_pct == 0.0
print(f"  缺失数据时正确产生 warning: {result.warnings[0]}")


# -----------------------------------------------------------------------------
# 8. 空场景列表
# -----------------------------------------------------------------------------
print("=" * 70)
print("8. 空场景列表")
print("=" * 70)

portfolio = _make_tech_bank_portfolio()
result = compute_stress_test(portfolio, dfs_map={}, scenario_ids=[], industry_lookup=_industry_lookup)
assert len(result.scenarios) == 0
_assert_close(result.total_loss_pct, 0.0)
_assert_close(result.total_loss_amount, 0.0)
_assert_close(result.risk_score, 0.0)
print("  空场景列表返回零损失结果")


# -----------------------------------------------------------------------------
# 9. overlay 汇总逻辑
# -----------------------------------------------------------------------------
print("=" * 70)
print("9. overlay 汇总逻辑")
print("=" * 70)

portfolio = [{"code": "STRESS", "weight": 1.0, "amount": 100000.0}]
df = _make_historical_df("STRESS", "2007-10-01", peak_price=120.0, trough_price=80.0, n_days=260)

# 同时跑一个历史场景与一个已注册的板块场景（科技板块回调 20%）
# 为了让板块场景生效，需要把 STRESS 映射到科技板块（电子）
result_worst = compute_stress_test(
    portfolio,
    dfs_map={"STRESS": df},
    scenario_ids=["2008年金融危机", "科技板块回调20%"],
    industry_lookup=lambda _c: "电子",
)
result_overlay = compute_stress_test(
    portfolio,
    dfs_map={"STRESS": df},
    scenario_ids=["2008年金融危机", "科技板块回调20%"],
    industry_lookup=lambda _c: "电子",
    overlay=True,
)

assert len(result_worst.scenarios) == 2, f"期望 2 个场景，实际 {len(result_worst.scenarios)}"
hist_loss = result_worst.scenarios[0].portfolio_loss_pct
sector_loss = result_worst.scenarios[1].portfolio_loss_pct
_assert_close(result_worst.total_loss_pct, min(hist_loss, sector_loss), tol=1e-6)
_assert_close(result_overlay.total_loss_pct, hist_loss + sector_loss, tol=1e-6)
print(f"  非 overlay 总损失（取最差）: {result_worst.total_loss_pct:.2f}%")
print(f"  overlay 总损失（简单相加）: {result_overlay.total_loss_pct:.2f}%")


# -----------------------------------------------------------------------------
# 10. 可选：基于 FileVisitor 的随机组合示例
# -----------------------------------------------------------------------------
print("=" * 70)
print("10. 随机组合压力测试示例（FileVisitor）")
print("=" * 70)

try:
    from infra_structure.data_engine.visitor.file_visitor import FileVisitor

    file_visitor = FileVisitor("basic", "stock", "market", "d1", "time_series").data_set()
    dfs = [file_visitor.random_one() for _ in range(5)]
    weights = [0.1, 0.2, 0.3, 0.3, 0.1]
    portfolio = [
        {"code": str(df["code"].iloc[0]), "weight": w, "amount": w * 100000.0}
        for df, w in zip(dfs, weights)
    ]
    dfs_map = {str(df["code"].iloc[0]): df for df in dfs}

    # 随机股票的行业查询可能失败，这里用自定义 lookup 保证板块场景可运行
    def _random_industry_lookup(code: str) -> Optional[str]:
        # 让组合中的股票命中科技板块，便于观察板块压力结果
        return "电子"

    random_result = compute_stress_test(
        portfolio,
        dfs_map=dfs_map,
        scenario_ids=["科技板块回调20%"],
        industry_lookup=_random_industry_lookup,
    )
    print(f"  组合标的: {[a['code'] for a in portfolio]}")
    print(f"  板块场景损失: {random_result.total_loss_pct:.2f}%")
    print(f"  风险等级    : {random_result.risk_level}")
except Exception as exc:  # noqa: BLE001
    print(f"  FileVisitor 示例跳过（环境依赖不满足）: {exc}")


# -----------------------------------------------------------------------------
# 汇总
# -----------------------------------------------------------------------------
print("=" * 70)
print("t_compute_stress.py 所有基础校验通过")
print("=" * 70)
