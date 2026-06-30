import math

import pandas as pd

from recommender.portfolio_advisor.data_read import load_all
from recommender.portfolio_advisor.dimension.drawdown_control import (
    calculate_portfolio_mdd,
    normalize_mdd_to_score,
)

data = load_all()

df_1: pd.DataFrame = data["df_1"]
df_2: pd.DataFrame = data["df_2"]
df_3: pd.DataFrame = data["df_3"]
df_4: pd.DataFrame = data["df_4"]
df_5: pd.DataFrame = data["df_5"]


def _fmt(value: float) -> str:
    """格式化输出，兼容 nan。"""
    return f"{value:.4f}" if isinstance(value, (int, float)) and not math.isnan(value) else "nan"


# 选取 5 只股票构建组合
dfs = [df_1, df_2, df_3, df_4, df_5]
weights = [0.3, 0.25, 0.2, 0.15, 0.1]

# 一键计算组合最大回撤
print("=" * 60)
print(f"组合标的: {[df['code'].iloc[0] for df in dfs]}")
print(f"组合最大回撤 (MDD): {_fmt(calculate_portfolio_mdd(dfs, weights))}")

# 测试：将 MDD 归一化为 0-100 风险分数
print("=" * 60)
print("MDD -> 0-100 风险分数映射:")
for mdd in [0.0, 0.05, 0.10, 0.15, 0.20, 0.275, 0.35, 0.3624, 0.50, 0.60]:
    print(f"  MDD={mdd:>6.4f} -> Score={normalize_mdd_to_score(mdd):>6.2f}")

# 使用示例：先算 MDD，再映射为风险分数
portfolio_mdd = calculate_portfolio_mdd(dfs, weights)
print("=" * 60)
print(f"组合 MDD: {_fmt(portfolio_mdd)}")
print(f"组合风险分数 (0-100): {_fmt(normalize_mdd_to_score(portfolio_mdd))}")
