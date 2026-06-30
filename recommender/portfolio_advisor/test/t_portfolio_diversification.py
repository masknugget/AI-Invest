import math

import numpy as np
import pandas as pd

from recommender.portfolio_advisor.data_read import load_all
from recommender.portfolio_advisor.dimension.portfolio_diversification import (
    compute_enb_from_dataframes,
    effective_number_of_bets_weight_based,
    normalize_enb_to_score,
)

data = load_all()

df_1: pd.DataFrame = data["df_1"]
df_2: pd.DataFrame = data["df_2"]
df_3: pd.DataFrame = data["df_3"]
df_4: pd.DataFrame = data["df_4"]
df_5: pd.DataFrame = data["df_5"]


# 选取 5 只股票构建组合
dfs = [df_1, df_2, df_3, df_4, df_5]
n_assets = len(dfs)
weights = np.array([0.3, 0.25, 0.2, 0.15, 0.1])


def _fmt(value) -> str:
    """格式化输出，兼容 nan。"""
    return f"{value:.4f}" if isinstance(value, (int, float)) and not math.isnan(value) else "nan"


# 单个基于权重的有效下注数
print("=" * 60)
print("基于权重的有效下注数:")
print(f"ENB (weight-based): {_fmt(effective_number_of_bets_weight_based(weights))}")

# 测试：将 weight-based ENB 归一化为 0-100 分数
print("=" * 60)
print("ENB -> 0-100 分散度分数映射:")
for w in [
    [1.0],
    [0.9, 0.1],
    [0.5, 0.5],
    [0.6, 0.2, 0.2],
    [0.2, 0.2, 0.2, 0.2, 0.2],
    [0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1],
]:
    n = len(w)
    enb = effective_number_of_bets_weight_based(w)
    score = normalize_enb_to_score(enb, n)
    print(f"  N={n:>2d}, weights={w} -> ENB={enb:>7.4f}, Score={score:>7.2f}")

# 一键计算所有有效下注数指标
print("=" * 60)
print("一键计算所有有效下注数指标:")
metrics = compute_enb_from_dataframes(dfs, weights, enb_type="both")
for k, v in metrics.items():
    if isinstance(v, float):
        print(f"{k}: {_fmt(v)}")
    else:
        print(f"{k}: {v}")

# 使用示例：从组合数据得到 ENB，再映射为分散度分数
print("=" * 60)
print("组合分散度分数 (0-100):")
enb_weight = metrics["enb_weight_based"]
print(f"  ENB (weight-based): {_fmt(enb_weight)}")
print(f"  分散度分数: {_fmt(normalize_enb_to_score(enb_weight, n_assets))}")
