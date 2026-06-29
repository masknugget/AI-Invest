import math

import pandas as pd

from infra_structure.data_engine.visitor.file_visitor import FileVisitor
from research.portfolio_advisor.dimension.position_efficiency import (
    calculate_portfolio_sharpe_ratio,
    calculate_portfolio_sharpe_score,
    normalize_sharpe_to_score,
)

file_visitor = FileVisitor("basic", "stock", "market", "d1", "time_series").data_set()

df_1: pd.DataFrame = file_visitor.random_one()
df_2: pd.DataFrame = file_visitor.random_one()
df_3: pd.DataFrame = file_visitor.random_one()
df_4: pd.DataFrame = file_visitor.random_one()
df_5: pd.DataFrame = file_visitor.random_one()


def _fmt(value: float) -> str:
    """格式化输出，兼容 nan。"""
    return f"{value:.4f}" if isinstance(value, (int, float)) and not math.isnan(value) else "nan"


# 选取 5 只股票构建组合
dfs = [df_1, df_2, df_3, df_4, df_5]
weights = [0.3, 0.25, 0.2, 0.15, 0.1]

# 测试：将夏普比率归一化为 0-100 分数
print("=" * 60)
print("Sharpe Ratio -> 0-100 分数映射:")
for sharpe in [-1.0, 0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 5.0]:
    print(f"  Sharpe={sharpe:>5.2f} -> Score={normalize_sharpe_to_score(sharpe):>7.2f}")

# 一键计算组合夏普比率
print("=" * 60)
print(f"组合标的: {[df['code'].iloc[0] for df in dfs]}")
sharpe_ratio = calculate_portfolio_sharpe_ratio(dfs, weights)
print(f"组合夏普比率: {_fmt(sharpe_ratio)}")
print(f"组合夏普分数 (0-100): {_fmt(normalize_sharpe_to_score(sharpe_ratio))}")

# 一键计算组合夏普得分（封装版）
print("=" * 60)
print("一键计算组合夏普得分:")
print(f"组合夏普得分: {_fmt(calculate_portfolio_sharpe_score(dfs, weights))}")
