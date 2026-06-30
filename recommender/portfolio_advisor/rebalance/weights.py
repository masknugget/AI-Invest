"""
权重再分配策略。

提供 1 对 1 替换时的权重处理，以及通用权重归一化。
"""

from typing import List, Set, Tuple

import numpy as np
import pandas as pd

from recommender.portfolio_advisor.rebalance.types import StockCandidate


WEIGHT_STRATEGIES: Set[str] = {"proportional", "equal", "fixed_new_weight"}


def _normalize_weights(weights: List[float]) -> List[float]:
    """将权重归一化为加和等于 1。"""
    arr = np.array(weights, dtype=float)
    total = arr.sum()
    if total <= 0:
        raise ValueError(f"权重总和必须为正，当前为 {total}")
    return (arr / total).tolist()


def replace_stock(
    codes: List[str],
    weights: List[float],
    dfs: List[pd.DataFrame],
    code_out: str,
    candidate: StockCandidate,
    weight_strategy: str = "proportional",
    fixed_new_weight: float = 0.0,
) -> Tuple[List[str], List[float], List[pd.DataFrame]]:
    """
    执行一次 1 对 1 替换：调出 code_out，调入 candidate。

    Parameters
    ----------
    codes : List[str]
        当前组合标的代码。
    weights : List[float]
        当前组合权重，和应为 1。
    dfs : List[pd.DataFrame]
        当前组合行情数据。
    code_out : str
        被调出的标的代码。
    candidate : StockCandidate
        被调入的候选股票。
    weight_strategy : str, default "proportional"
        权重再分配策略："proportional" / "equal" / "fixed_new_weight"。
    fixed_new_weight : float, default 0.0
        weight_strategy="fixed_new_weight" 时，指定调入标的的固定权重。

    Returns
    -------
    Tuple[List[str], List[float], List[pd.DataFrame]]
        新组合的 codes / weights / dfs，其中 weights 已归一化。
    """
    if weight_strategy not in WEIGHT_STRATEGIES:
        raise ValueError(f"不支持的权重策略: {weight_strategy}，可选: {WEIGHT_STRATEGIES}")

    if len(codes) != len(weights) or len(codes) != len(dfs):
        raise ValueError("codes / weights / dfs 长度必须一致")

    if code_out not in codes:
        raise ValueError(f"code_out {code_out} 不在当前组合中")

    out_idx = codes.index(code_out)
    weight_out = float(weights[out_idx])

    remaining_codes = [c for i, c in enumerate(codes) if i != out_idx]
    remaining_weights = [w for i, w in enumerate(weights) if i != out_idx]
    remaining_dfs = [dfs[i] for i in range(len(dfs)) if i != out_idx]

    n_new = len(remaining_codes) + 1

    if weight_strategy == "proportional":
        # 调入标的继承调出权重，剩余标的权重不变
        new_weights = remaining_weights + [weight_out]

    elif weight_strategy == "equal":
        # 所有标的等权
        new_weights = [1.0 / n_new] * n_new

    else:  # fixed_new_weight
        if not (0 < fixed_new_weight < 1):
            raise ValueError(f"fixed_new_weight 必须在 (0, 1) 之间，当前为 {fixed_new_weight}")
        remaining_total = sum(remaining_weights)
        if remaining_total <= 0:
            raise ValueError("剩余标的权重总和必须为正")
        scale = (1.0 - fixed_new_weight) / remaining_total
        new_weights = [w * scale for w in remaining_weights] + [fixed_new_weight]

    new_codes = remaining_codes + [candidate.code]
    new_dfs = remaining_dfs + [candidate.df]

    return new_codes, _normalize_weights(new_weights), new_dfs


def redistribute_weights(
    remaining_weights: List[float],
    n_new: int,
    total_removed_weight: float,
    weight_strategy: str,
    fixed_new_weight: float,
) -> List[float]:
    """
    通用权重再分配：已知剩余标的权重、调出总权重、调入数量，计算新权重。

    Parameters
    ----------
    remaining_weights : List[float]
        剩余原标的权重。
    n_new : int
        调入标的数量。
    total_removed_weight : float
        被调出标的的权重总和。
    weight_strategy : str
        权重策略。
    fixed_new_weight : float
        fixed_new_weight 策略下，所有调入标的的总固定权重。

    Returns
    -------
    List[float]
        新组合权重（剩余 + 调入），尚未归一化。
    """
    if weight_strategy not in WEIGHT_STRATEGIES:
        raise ValueError(f"不支持的权重策略: {weight_strategy}，可选: {WEIGHT_STRATEGIES}")

    n_remaining = len(remaining_weights)

    if weight_strategy == "proportional":
        # 调入标的均分调出权重，剩余标的权重不变
        return remaining_weights + [total_removed_weight / n_new] * n_new

    if weight_strategy == "equal":
        # 所有标的等权
        return [1.0 / (n_remaining + n_new)] * (n_remaining + n_new)

    # fixed_new_weight
    if not (0 < fixed_new_weight < 1):
        raise ValueError(f"fixed_new_weight 必须在 (0, 1) 之间，当前为 {fixed_new_weight}")
    weight_per_new = fixed_new_weight / n_new
    remaining_total = sum(remaining_weights)
    if remaining_total <= 0:
        raise ValueError("剩余标的权重总和必须为正")
    scale = (1.0 - fixed_new_weight) / remaining_total
    return [w * scale for w in remaining_weights] + [weight_per_new] * n_new
