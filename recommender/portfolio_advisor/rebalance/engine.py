"""
调仓建议引擎入口。

仅负责参数校验与模块编排，将具体计算委托给 search / scoring / weights / loader 等子模块。
不做多轮贪心迭代。

当前优化仅依赖 stock_dimension_scores.jsonl 中的预计算五维得分，不再加载
行情 DataFrame 进行重算。
"""

from typing import Dict, List

from recommender.portfolio_advisor.rebalance.constraints import clamp_max_actions
from recommender.portfolio_advisor.rebalance.loader import (
    get_current_stock_scores,
    load_candidate_pool_from_jsonl_as_pool,
)
from recommender.portfolio_advisor.rebalance.scoring import evaluate_portfolio_from_scores
from recommender.portfolio_advisor.rebalance.search import search_rebalance_plans, search_rebalance_plans_by_scores
from recommender.portfolio_advisor.rebalance.types import CandidatePool, RebalancePlan
from recommender.portfolio_advisor.rebalance.weights import WEIGHT_STRATEGIES


def suggest_rebalance(
    current_codes: List[str],
    current_weights: List[float],
    scores_path: str,
    objective: str = "composite_score",
    max_actions: int = 1,
    min_improvement: float = 0.0,
    weight_strategy: str = "proportional",
    top_k: int = 3,
    verbose: bool = False,
    fixed_new_weight: float = 0.0,
) -> List[RebalancePlan]:
    """
    生成调仓建议。

    仅依赖 stock_dimension_scores.jsonl 中的预计算五维得分，不加载行情 DataFrame。

    Parameters
    ----------
    current_codes : List[str]
        当前组合标的代码。
    current_weights : List[float]
        当前组合权重，和应为 1。
    scores_path : str
        stock_dimension_scores.jsonl 文件路径。
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

    Returns
    -------
    List[RebalancePlan]
        按 improvement 降序排列的调仓方案列表。
    """
    if weight_strategy not in WEIGHT_STRATEGIES:
        raise ValueError(f"不支持的权重策略: {weight_strategy}，可选: {WEIGHT_STRATEGIES}")

    n_current = len(current_codes)
    if n_current == 0:
        raise ValueError("当前组合不能为空")
    if len(current_weights) != n_current:
        raise ValueError("current_weights 长度必须与 current_codes 一致")

    current_stock_scores = get_current_stock_scores(current_codes, scores_path)
    if len(current_stock_scores) != n_current:
        raise ValueError("current_stock_scores 长度必须与 current_codes 一致")

    current_codes_set = set(current_codes)
    candidate_pool = load_candidate_pool_from_jsonl_as_pool(scores_path, fetch_full_df=False)
    candidates = [
        c for c in candidate_pool.candidates if c.code not in current_codes_set
    ]
    if len(candidates) == 0:
        raise ValueError("候选股票池不能为空")
    candidate_pool = CandidatePool(candidates=candidates)

    max_actions = clamp_max_actions(max_actions, n_current)

    score_current, portfolio_current = evaluate_portfolio_from_scores(
        current_codes, current_stock_scores, current_weights, objective
    )

    if verbose:
        print(f"当前目标得分 ({objective}): {score_current:.4f}")

    plans = search_rebalance_plans(
        current_codes,
        current_weights,
        current_stock_scores,
        candidate_pool,
        score_current,
        portfolio_current,
        objective,
        max_actions,
        min_improvement,
        weight_strategy,
        fixed_new_weight,
        verbose=verbose,
    )

    return plans[:top_k]


def suggest_rebalance_by_scores(
    current_codes: List[str],
    current_weights: List[float],
    current_stock_scores: List[Dict[str, float]],
    candidate_pool: CandidatePool,
    objective: str = "composite_score",
    max_actions: int = 1,
    min_improvement: float = 0.0,
    weight_strategy: str = "proportional",
    top_k: int = 3,
    verbose: bool = False,
    fixed_new_weight: float = 0.0,
) -> List[RebalancePlan]:
    """
    基于预计算维度得分生成调仓建议，不依赖 DataFrame。

    Parameters
    ----------
    current_codes : List[str]
        当前组合标的代码。
    current_weights : List[float]
        当前组合权重，和应为 1。
    current_stock_scores : List[Dict[str, float]]
        当前组合每只股票的五维得分。
    candidate_pool : CandidatePool
        候选股票池，每个候选需包含 dimension_scores。
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

    Returns
    -------
    List[RebalancePlan]
        按 improvement 降序排列的调仓方案列表。
    """
    if weight_strategy not in WEIGHT_STRATEGIES:
        raise ValueError(f"不支持的权重策略: {weight_strategy}，可选: {WEIGHT_STRATEGIES}")

    n_current = len(current_codes)
    if n_current == 0:
        raise ValueError("当前组合不能为空")
    if len(current_weights) != n_current:
        raise ValueError("current_weights 长度必须与 current_codes 一致")
    if len(current_stock_scores) != n_current:
        raise ValueError("current_stock_scores 长度必须与 current_codes 一致")

    candidates = list(candidate_pool.candidates)
    if len(candidates) == 0:
        raise ValueError("候选股票池不能为空")

    max_actions = clamp_max_actions(max_actions, n_current)

    score_current, portfolio_current = evaluate_portfolio_from_scores(
        current_codes, current_stock_scores, current_weights, objective
    )

    if verbose:
        print(f"当前目标得分 ({objective}): {score_current:.4f}")

    plans = search_rebalance_plans_by_scores(
        current_codes,
        current_weights,
        current_stock_scores,
        candidate_pool,
        score_current,
        portfolio_current,
        objective,
        max_actions,
        min_improvement,
        weight_strategy,
        fixed_new_weight,
        verbose=verbose,
    )

    return plans[:top_k]
