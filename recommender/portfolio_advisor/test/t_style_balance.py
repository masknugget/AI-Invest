import math

import numpy as np
import pandas as pd

from recommender.portfolio_advisor.data_read import load_all
from recommender.portfolio_advisor.dimension.style_balance import (
    calculate_style_hhi,
    normalize_style_hhi_to_score,
)

data = load_all()

df_1: pd.DataFrame = data["df_1"]
df_2: pd.DataFrame = data["df_2"]
df_3: pd.DataFrame = data["df_3"]
df_4: pd.DataFrame = data["df_4"]
df_5: pd.DataFrame = data["df_5"]


def _fmt(value) -> str:
    """格式化输出，兼容 nan。"""
    return f"{value:.4f}" if isinstance(value, (int, float)) and not math.isnan(value) else "nan"


# 选取 5 只股票构建组合
dfs = [df_1, df_2, df_3, df_4, df_5]
weights = [0.3, 0.25, 0.2, 0.15, 0.1]

# 一键计算风格均衡指标
print("=" * 60)
print("一键计算风格均衡指标:")
metrics = calculate_style_hhi(dfs, weights)
for k, v in metrics.items():
    if isinstance(v, float):
        print(f"{k}: {_fmt(v)}")
    else:
        print(f"{k}: {v}")

# 测试：将风格 HHI 归一化为 0-100 均衡度分数
print("=" * 60)
print("Style HHI -> 0-100 均衡度分数映射:")
n_styles = int(metrics["total_styles"])  # type: ignore[arg-type]
test_hhi_values = [1.0, 0.75, 0.5, 0.25, 1.0 / n_styles]
for hhi in test_hhi_values:
    print(
        f"  HHI={hhi:>6.4f}, N={n_styles} "
        f"-> Score={normalize_style_hhi_to_score(hhi, n_styles):>7.2f}"
    )

# 使用示例：从组合风格指标得到 HHI，再映射为均衡度分数
print("=" * 60)
print("组合风格均衡度分数 (0-100):")
style_hhi = float(metrics["style_hhi"])  # type: ignore[arg-type]
print(f"  风格 HHI: {_fmt(style_hhi)}")
print(f"  风格均衡度分数: {_fmt(normalize_style_hhi_to_score(style_hhi, n_styles))}")
