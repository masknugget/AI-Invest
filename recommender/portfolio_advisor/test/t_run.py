import math

import pandas as pd

from recommender.portfolio_advisor.data_read import load_all
from recommender.portfolio_advisor.dimension.run import compute_portfolio_dimensions

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

# 计算五维诊断
print("=" * 60)
print(f"组合标的: {[df['code'].iloc[0] for df in dfs]}")
print(f"组合权重: {weights}")

result = compute_portfolio_dimensions(dfs, weights)

print(f"抗回撤控制得分 : {_fmt(result.drawdown_control.score)}")
print(f"资产分散得分   : {_fmt(result.portfolio_diversification.score)}")
print(f"持仓性价比得分 : {_fmt(result.position_efficiency.score)}")
print(f"收益稳定得分   : {_fmt(result.return_stability.score)}")
print(f"风格均衡得分   : {_fmt(result.style_balance.score)}")
print("=" * 60)
print(f"综合健康分     : {_fmt(result.composite_score)}")
print(f"几何加权综合分 : {_fmt(result.geometric_composite_score)}")
