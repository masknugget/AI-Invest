"""
调仓方案构造。

根据调出/调入标的生成新的组合（codes/weights/dfs）以及可解释的 RebalanceAction。
"""

from typing import List, Tuple

from recommender.portfolio_advisor.rebalance.types import RebalanceAction, StockCandidate
from recommender.portfolio_advisor.rebalance.weights import redistribute_weights


def build_replacement_portfolio(
    codes: List[str],
    weights: List[float],
    dfs,
    out_indices: Tuple[int, ...],
    in_candidates: Tuple[StockCandidate, ...],
    weight_strategy: str,
    fixed_new_weight: float,
) -> Tuple[List[str], List[float], List, float]:
    """
    构造替换后的新组合。

    Returns
    -------
    Tuple[List[str], List[float], List[pd.DataFrame], float]
        新组合的 codes / weights / dfs，以及总调出权重。
    """
    out_indices_set = set(out_indices)
    remaining_codes = [c for i, c in enumerate(codes) if i not in out_indices_set]
    remaining_weights = [w for i, w in enumerate(weights) if i not in out_indices_set]
    remaining_dfs = [dfs[i] for i in range(len(dfs)) if i not in out_indices_set]

    total_removed_weight = sum(weights[i] for i in out_indices)
    n_new = len(in_candidates)

    new_codes = remaining_codes + [c.code for c in in_candidates]
    new_dfs = remaining_dfs + [c.df for c in in_candidates]

    new_weights = redistribute_weights(
        remaining_weights,
        n_new,
        total_removed_weight,
        weight_strategy,
        fixed_new_weight,
    )

    # 归一化保证安全和为 1
    total = sum(new_weights)
    if total <= 0:
        raise ValueError("新组合权重总和必须为正")
    new_weights = [w / total for w in new_weights]

    return new_codes, new_weights, new_dfs, total_removed_weight


def make_actions(
    codes: List[str],
    out_indices: Tuple[int, ...],
    in_candidates: Tuple[StockCandidate, ...],
    new_weights: List[float],
    weight_strategy: str,
    improvement: float,
) -> List[RebalanceAction]:
    """为一次替换生成可解释的 RebalanceAction 列表。"""
    n_remaining = len(codes) - len(out_indices)
    actions: List[RebalanceAction] = []

    for k, out_idx in enumerate(out_indices):
        code_out = codes[out_idx]
        code_in = in_candidates[k].code if k < len(in_candidates) else None
        weight_in = new_weights[n_remaining + k] if k < len(in_candidates) else 0.0

        reason = f"替换以提升目标得分，预计提升 {improvement:.4f}"
        if weight_strategy == "equal":
            reason += "；采用等权重再分配"
        elif weight_strategy == "fixed_new_weight":
            reason += "；调入标的采用固定权重"
        else:
            reason += "；调入标的继承调出权重"

        actions.append(
            RebalanceAction(
                action_type="replace",
                code_out=code_out,
                code_in=code_in,
                weight_out=0.0,  # 具体数值在 plan 中以权重形式体现
                weight_in=weight_in,
                reason=reason,
            )
        )
    return actions
