"""
调仓约束校验。

包括 max_actions 范围截断、组合重叠交易日检查等。
"""

import warnings
from typing import List

import pandas as pd


def clamp_max_actions(max_actions: int, n_current: int) -> int:
    """校验并截断 max_actions 到合法范围 [1, min(3, n_current)]。"""
    if max_actions < 1:
        raise ValueError(f"max_actions 必须 >= 1，当前为 {max_actions}")
    if max_actions > 3:
        warnings.warn(f"max_actions {max_actions} 超过上限 3，自动截断为 3", stacklevel=3)
        max_actions = 3
    if max_actions > n_current:
        warnings.warn(
            f"max_actions {max_actions} 大于当前组合标的数 {n_current}，自动截断为 {n_current}",
            stacklevel=3,
        )
        max_actions = n_current
    return max_actions


def count_overlap_days(dfs: List[pd.DataFrame]) -> int:
    """计算所有 DataFrame 日期列的交集长度。"""
    if not dfs:
        return 0
    dates = set(dfs[0]["date"])
    for df in dfs[1:]:
        dates &= set(df["date"])
    return len(dates)
