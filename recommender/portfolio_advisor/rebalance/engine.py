"""
调仓建议引擎入口。

仅负责参数校验与模块编排，将具体计算委托给 search / scoring / weights / constraints 等子模块。
不做多轮贪心迭代。
"""

import warnings
from typing import List, Optional

from recommender.portfolio_advisor.rebalance.constraints import clamp_max_actions, count_overlap_days
from recommender.portfolio_advisor.rebalance.scoring import evaluate_portfolio
from recommender.portfolio_advisor.rebalance.search import search_rebalance_plans
from recommender.portfolio_advisor.rebalance.types import CandidatePool, RebalancePlan
from recommender.portfolio_advisor.rebalance.weights import WEIGHT_STRATEGIES


def suggest_rebalance(
    current_dfs: List,
    current_weights: List[float],
    candidate_pool: CandidatePool,
    objective: str = "geometric_composite_score",
    max_actions: int = 1,
    min_improvement: float = 0.0,
    weight_strategy: str = "proportional",
    top_k: int = 3,
    verbose: bool = False,
    fixed_new_weight: float = 0.0,
    min_overlap_days: Optional[int] = None,
) -> List[RebalancePlan]:
    """
    生成调仓建议。

    Parameters
    ----------
    current_dfs : List[pd.DataFrame]
        当前组合各标的行情数据。
    current_weights : List[float]
        当前组合权重，和应为 1。
    candidate_pool : CandidatePool
        候选股票池。
    objective : str, default "geometric_composite_score"
        优化目标："composite_score" / "geometric_composite_score" /
        "min_dimension_score" / "dimension:<name>"。
    max_actions : int, default 1
        单次最多同时替换几只股票，取值范围 [1, 3]，且不得大于当前组合标的个数 N。
    min_improvement : float, default 0.0
        最小可接受得分提升，低于该值的方案被过滤。
    weight_strategy : str, default "proportional"
        权重再分配策略："proportional" / "equal" / "fixed_new_weight"。
    top_k : int, default 3
        返回前 K 个最优方案。
    verbose : bool, default False
        是否打印中间过程。
    fixed_new_weight : float, default 0.0
        weight_strategy="fixed_new_weight" 时每只调入标的的固定权重。
    min_overlap_days : Optional[int], default None
        若指定，则要求当前组合及每个新组合的重叠交易日数不低于该阈值；
        不足时跳过该方案并发出警告。

    Returns
    -------
    List[RebalancePlan]
        按 improvement 降序排列的调仓方案列表。
    """
    if weight_strategy not in WEIGHT_STRATEGIES:
        raise ValueError(f"不支持的权重策略: {weight_strategy}，可选: {WEIGHT_STRATEGIES}")

    n_current = len(current_dfs)
    if n_current == 0:
        raise ValueError("当前组合不能为空")
    if len(current_weights) != n_current:
        raise ValueError("current_weights 长度必须与 current_dfs 一致")

    candidates = list(candidate_pool.candidates)
    if len(candidates) == 0:
        raise ValueError("候选股票池不能为空")

    max_actions = clamp_max_actions(max_actions, n_current)

    current_codes = [str(df["code"].iloc[0]) for df in current_dfs]

    if min_overlap_days is not None and count_overlap_days(current_dfs) < min_overlap_days:
        warnings.warn(
            f"当前组合重叠交易日 {count_overlap_days(current_dfs)} 少于阈值 {min_overlap_days}，"
            "结果可能不可靠。",
            stacklevel=2,
        )

    score_current, portfolio_current = evaluate_portfolio(
        current_codes, current_weights, current_dfs, objective
    )

    if verbose:
        print(f"当前目标得分 ({objective}): {score_current:.4f}")

    plans = search_rebalance_plans(
        current_codes,
        current_weights,
        current_dfs,
        candidate_pool,
        score_current,
        portfolio_current,
        objective,
        max_actions,
        min_improvement,
        weight_strategy,
        fixed_new_weight,
        min_overlap_days=min_overlap_days,
        verbose=verbose,
    )

    return plans[:top_k]
