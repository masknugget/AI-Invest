import math

import pandas as pd

from infra_structure.data_engine.visitor.file_visitor import FileVisitor
from research.portfolio_advisor.dimension.return_stability import (
    calculate_annualized_volatility,
    normalize_volatility_to_score,
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


# 单只股票年化波动率
print("=" * 60)
print(f"股票代码: {df_1['code'].iloc[0]}")
print(f"单股年化波动率: {_fmt(calculate_annualized_volatility([df_1], [1.0]))}")

# 投资组合年化波动率
print("=" * 60)
print("投资组合年化波动率:")
dfs = [df_1, df_2, df_3, df_4, df_5]
weights = [0.3, 0.25, 0.2, 0.15, 0.1]
portfolio_volatility = calculate_annualized_volatility(dfs, weights)
print(f"组合年化波动率: {_fmt(portfolio_volatility)}")

# 测试：将年化波动率归一化为 0-100 风险分数
print("=" * 60)
print("Volatility -> 0-100 风险分数映射:")
for vol in [0.0, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.60, 0.80, 1.0]:
    print(f"  Vol={vol:>6.4f} -> Score={normalize_volatility_to_score(vol):>7.2f}")

# 使用示例：先算组合年化波动率，再映射为风险分数
print("=" * 60)
print(f"组合风险分数 (0-100): {_fmt(normalize_volatility_to_score(portfolio_volatility))}")
