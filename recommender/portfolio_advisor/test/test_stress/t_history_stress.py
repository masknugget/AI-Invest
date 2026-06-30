"""
history_stress.py 使用示例与简单校验。

运行方式：
    python research/portfolio_advisor/test/test_stress/t_history_stress.py
"""

import math
import sys
import types
from typing import Any

import pandas as pd

# mock openai，避免 recommender/__init__.py 链式导入失败
if "openai" not in sys.modules:
    _openai_mock = types.ModuleType("openai")
    _openai_mock.OpenAI = type("OpenAI", (), {})
    sys.modules["openai"] = _openai_mock

from recommender.portfolio_advisor.stress_portfolio.history_stress import (
    calculate_historical_drawdown,
    calculate_historical_scenario_result,
    compute_historical_stress,
    simulate_portfolio_drawdown,
    list_historical_scenario_names,
)
from recommender.portfolio_advisor.stress_portfolio.const import build_scenarios


def _fmt(value: Any) -> str:
    """格式化浮点数输出，兼容 nan。"""
    if isinstance(value, (int, float)) and not math.isnan(value):
        return f"{value:.4f}"
    return str(value)


# -----------------------------------------------------------------------------
# 1. 查看可用历史场景
# -----------------------------------------------------------------------------
print("=" * 60)
print("可用历史场景")
print("=" * 60)
names = list_historical_scenario_names()
print(f"场景列表: {names}")

# -----------------------------------------------------------------------------
# 2. 构造一只测试股票：100 -> 120 -> 80，最大回撤约 -33%
# -----------------------------------------------------------------------------
dates = pd.date_range("2008-01-01", periods=260, freq="B").strftime("%Y-%m-%d")
n_up = 130
prices = [100 + (120 - 100) / n_up * i for i in range(n_up)]
prices += [120 + (80 - 120) / (len(dates) - n_up) * i for i in range(1, len(dates) - n_up + 1)]
df_a = pd.DataFrame({
    "date": dates,
    "code": "TEST_A",
    "close": prices,
})

# -----------------------------------------------------------------------------
# 3. 单票最大回撤
# -----------------------------------------------------------------------------
print("=" * 60)
print("单票历史最大回撤")
print("=" * 60)

drawdown = calculate_historical_drawdown(
    df_a,
    {"start_date": "2008-01-01", "end_date": "2008-12-31"},
)
assert drawdown is not None
print(f"代码      : {drawdown['code']}")
print(f"最大回撤  : {_fmt(drawdown['max_drawdown'] * 100)}%")
print(f"峰值日期  : {drawdown['peak_date']}")
print(f"谷值日期  : {drawdown['trough_date']}")

# -----------------------------------------------------------------------------
# 4. 组合在单个历史场景下的损失
# -----------------------------------------------------------------------------
print("=" * 60)
print("单个历史场景压力测试")
print("=" * 60)

portfolio_df = pd.DataFrame({
    "code": ["TEST_A"],
    "weight": [1.0],
    "amount": [100000.0],
})
scenario = build_scenarios(["2008年金融危机"])[0]
result = calculate_historical_scenario_result(
    portfolio_df,
    scenario,
    {"TEST_A": df_a},
)
print(f"场景名称      : {result['scenario_name']}")
print(f"场景区间      : {result['start_date']} ~ {result['end_date']}")
print(f"基准回撤      : {result['benchmark_drawdown']}")
print(f"组合总市值    : {result['portfolio_value']}")
print(f"组合损失比例  : {_fmt(result['portfolio_loss_pct'])}%")
print(f"组合损失金额  : {_fmt(result['portfolio_loss_amount'])}")
print(f"逐票明细:")
for a in result["per_asset"]:
    print(f"  {a['code']}  回撤={a['drawdown']:.2%}  损失={a['loss_amount']:.0f}  "
          f"峰值={a['peak_date']}  谷值={a['trough_date']}")

# -----------------------------------------------------------------------------
# 5. 批量历史场景计算
# -----------------------------------------------------------------------------
print("=" * 60)
print("批量历史场景计算")
print("=" * 60)

portfolio = [{"code": "TEST_A", "weight": 1.0, "amount": 100000.0}]
results = compute_historical_stress(portfolio, {"TEST_A": df_a})
for r in results:
    print(f"  {r['scenario_name']}: {r['portfolio_loss_pct']}%  (基准 {r['benchmark_drawdown']})")

# -----------------------------------------------------------------------------
# 6. 组合净值 / 回撤时间序列模拟
# -----------------------------------------------------------------------------
print("=" * 60)
print("组合净值与回撤时间序列")
print("=" * 60)

df_b = pd.DataFrame({
    "date": dates,
    "code": "TEST_B",
    "close": [100] * len(dates),  # 无波动
})
dd_df = simulate_portfolio_drawdown([df_a, df_b], [0.5, 0.5])
print(f"时间序列长度: {len(dd_df)}")
print(f"期末累计净值: {_fmt(dd_df['portfolio_value'].iloc[-1])}")
print(f"最大回撤    : {_fmt(dd_df['drawdown'].min() * 100)}%")
print(dd_df.head(3).to_string(index=False))
print("...")
print(dd_df.tail(3).to_string(index=False))

# -----------------------------------------------------------------------------
# 7. 可选：用本地 parquet 数据跑一次
# -----------------------------------------------------------------------------
print("=" * 60)
print("本地真实数据示例")
print("=" * 60)

try:
    from recommender.portfolio_advisor.data_read import load_all

    data = load_all()
    df_real = data["df_1"]
    code_real = str(df_real["code"].iloc[0])

    drawdown_real = calculate_historical_drawdown(
        df_real,
        {"start_date": "2022-01-01", "end_date": "2022-12-31"},
    )
    if drawdown_real is None:
        print(f"  股票 {code_real} 在指定场景区间内无数据")
    else:
        print(f"  股票 {code_real} 在 2022 年场景下最大回撤: {_fmt(drawdown_real['max_drawdown'] * 100)}%")
except Exception as exc:  # noqa: BLE001
    print(f"  本地数据示例跳过（环境依赖不满足）: {exc}")

print("=" * 60)
print("t_history_stress.py 运行完成")
print("=" * 60)
