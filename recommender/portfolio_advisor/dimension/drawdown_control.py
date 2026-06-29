"""
    最大回撤 Maximum Drawdown (MDD)

"""

import pandas as pd
import numpy as np
from typing import List, Union


def calculate_portfolio_mdd(
    dfs: List[pd.DataFrame],
    weights: Union[List[float], np.ndarray],
    price_col: str = 'close',
) -> float:
    """
    计算投资组合的最大回撤（Maximum Drawdown, MDD）。

    最大回撤定义为：在选定周期内，从资产最高点到后续最低点的最大跌幅。
    数学表达：MDD = max_{t} [(P_{peak} - P_{t}) / P_{peak}]

    参数:
        dfs: 包含n个资产数据的DataFrame列表，每个DataFrame的列名相同，
             且必须包含'date'和price_col指定的价格列。n >= 1。
        weights: 投资组合权重列表或数组，长度等于dfs长度，所有权重之和应为1。
                 例如 [0.5, 0.3, 0.2]。
        price_col: 用于计算收益率的价格列名，默认为'close'。

    返回:
        float: 投资组合的最大回撤值（非负值，例如0.15表示15%的最大回撤）。
               若数据不足返回0.0。

    注意:
        无风险利率在最大回撤计算中不需要使用。
    """
    # 输入校验
    n_assets = len(dfs)
    assert n_assets >= 1, "资产数量必须至少为1"
    assert len(weights) == n_assets, f"权重数量({len(weights)})必须与资产数量({n_assets})一致"
    assert abs(sum(weights) - 1.0) < 1e-6, f"权重之和必须等于1，当前为{sum(weights)}"

    # 按日期对齐所有资产数据，取交集（inner join）
    merged = dfs[0][['date', price_col]].copy()
    merged = merged.rename(columns={price_col: 'p0'})

    for i in range(1, n_assets):
        df_i = dfs[i][['date', price_col]].copy()
        df_i = df_i.rename(columns={price_col: f'p{i}'})
        merged = merged.merge(df_i, on='date', how='inner')

    # 按日期排序
    merged = merged.sort_values('date').reset_index(drop=True)

    price_cols = [f'p{i}' for i in range(n_assets)]
    prices = merged[price_cols]

    # 若对齐后无数据，返回0
    if prices.empty or len(prices) < 2:
        return 0.0

    # 计算各资产的日收益率（简单收益率）
    asset_returns = prices.pct_change().dropna()

    # 若去除NA后无数据，返回0
    if asset_returns.empty:
        return 0.0

    # 计算组合日收益率：加权求和
    weights_arr = np.array(weights, dtype=float)
    portfolio_returns = asset_returns @ weights_arr  # (T, n) @ (n,) -> (T,)

    # 计算累计净值曲线（从1开始）
    cumulative_value = (1 + portfolio_returns).cumprod()

    # 计算历史峰值（截至当前时刻的最大累计净值）
    running_peak = cumulative_value.cummax()

    # 计算回撤序列
    drawdown_series = (cumulative_value - running_peak) / running_peak

    # 最大回撤为回撤序列的最小值（最负值）的绝对值
    mdd = -drawdown_series.min()

    return float(mdd)


def normalize_mdd_to_score(mdd: float) -> float:
    """
    将最大回撤（MDD）归一化为 0-100 的风险分数。

    采用阈值分段线性映射，区间划分如下：
        - MDD ≤ 10%   : 低风险，分数 0-20
        - 10% < MDD ≤ 20% : 中低风险，分数 20-50
        - 20% < MDD ≤ 35% : 中高风险，分数 50-80
        - 35% < MDD ≤ 50% : 高风险，分数 80-100
        - MDD > 50%   : 极高风险，分数 100（截断）

    参数:
        mdd: 最大回撤值，为小数形式（例如 0.3624 表示 36.24%）。
             必须为非负数。

    返回:
        float: 0-100 的风险分数，保留两位小数。

    示例:
        >>> normalize_mdd_to_score(0.3624)
        81.65
    """
    assert mdd >= 0, "MDD 必须为非负数"

    # 区间边界与对应分数
    if mdd <= 0.10:
        # [0, 0.10] -> [0, 20]
        score = (mdd / 0.10) * 20
    elif mdd <= 0.20:
        # (0.10, 0.20] -> (20, 50]
        score = 20 + (mdd - 0.10) / (0.20 - 0.10) * (50 - 20)
    elif mdd <= 0.35:
        # (0.20, 0.35] -> (50, 80]
        score = 50 + (mdd - 0.20) / (0.35 - 0.20) * (80 - 50)
    elif mdd <= 0.50:
        # (0.35, 0.50] -> (80, 100]
        score = 80 + (mdd - 0.35) / (0.50 - 0.35) * (100 - 80)
    else:
        # > 0.50: 截断为 100
        score = 100.0

    return round(score, 2)


# ========== 使用示例 ==========
if __name__ == "__main__":
    # 假设已调用 calculate_portfolio_mdd 得到 mdd 值
    mdd = 0.3624  # 36.24%
    risk_score = normalize_mdd_to_score(mdd)
    print(f"组合最大回撤: {mdd:.4f} ({mdd*100:.2f}%)")
    print(f"风险分数 (0-100): {risk_score}")

    # 各区间边界验证
    test_cases = [0.0, 0.05, 0.10, 0.15, 0.20, 0.275, 0.35, 0.3624, 0.50, 0.60]
    for tc in test_cases:
        print(f"MDD={tc:>6.4f} -> Score={normalize_mdd_to_score(tc):>6.2f}")