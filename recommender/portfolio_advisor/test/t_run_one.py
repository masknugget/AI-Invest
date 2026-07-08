import math

import pandas as pd

from recommender.portfolio_advisor.data_read import load_all
from recommender.portfolio_advisor.dimension.run_one import compute_stock_dimensions

data = load_all()

# 选取第一只股票做单资产五维诊断
df: pd.DataFrame = data["df_1"]


def _fmt(value: float) -> str:
    """格式化输出，兼容 nan。"""
    return f"{value:.4f}" if isinstance(value, (int, float)) and not math.isnan(value) else "nan"


# 计算单只股票五维诊断
print("=" * 60)
print(f"标的代码: {df['code'].iloc[0]}")

result = compute_stock_dimensions(df)

print(f"抗回撤控制得分 : {_fmt(result.drawdown_control.score)}")
print(f"资产分散得分   : {_fmt(result.portfolio_diversification.score)}")
print(f"持仓性价比得分 : {_fmt(result.position_efficiency.score)}")
print(f"收益稳定得分   : {_fmt(result.return_stability.score)}")
print(f"风格均衡得分   : {_fmt(result.style_balance.score)}")
print("=" * 60)
print(f"综合健康分     : {_fmt(result.composite_score)}")
print(f"几何加权综合分 : {_fmt(result.geometric_composite_score)}")
