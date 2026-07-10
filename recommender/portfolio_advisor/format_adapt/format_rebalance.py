"""
调仓建议格式化适配器。

将 RebalancePlan / RebalanceAction 转换为前端友好的 dict 结构，
并可选择调用 LLM 生成详细的调入/调出原因。
"""

from typing import Any, Dict, List, Optional

from recommender.portfolio_advisor.analyst import reason_llm
from recommender.portfolio_advisor.rebalance.types import RebalancePlan


def format_rebalance_action(
    action,
    all_scores: Dict[str, Dict[str, float]],
    score_before: float,
    score_after: float,
    improvement: float,
    objective: str = "composite_score",
    include_llm_reason: bool = True,
) -> Dict[str, Any]:
    """
    将单个 RebalanceAction 转换为 dict。

    Parameters
    ----------
    action : RebalanceAction
        调仓动作对象。
    all_scores : Dict[str, Dict[str, float]]
        所有股票的五维评分映射，key 为股票 code。
    score_before, score_after, improvement : float
        方案级得分信息。
    objective : str
        优化目标。
    include_llm_reason : bool
        是否调用 LLM 生成详细原因。

    Returns
    -------
    Dict[str, Any]
        {
            "code_out": ...,
            "code_in": ...,
            "weight_out": ...,
            "weight_in": ...,
            "reason": ...,
            "scores_out": {...},
            "scores_in": {...},
            "detailed_reason": "LLM 生成的说明"  # include_llm_reason=True 时
        }
    """
    code_out = action.code_out
    code_in = action.code_in
    scores_out = all_scores.get(code_out) if code_out else None
    scores_in = all_scores.get(code_in) if code_in else None

    result: Dict[str, Any] = {
        "code_out": code_out,
        "code_in": code_in,
        "weight_out": action.weight_out,
        "weight_in": action.weight_in,
        "reason": action.reason,
        "scores_out": scores_out,
        "scores_in": scores_in,
    }

    if include_llm_reason:
        detailed_reason = reason_llm(
            code_out=code_out,
            code_in=code_in,
            weight_out=action.weight_out,
            weight_in=action.weight_in,
            score_before=score_before,
            score_after=score_after,
            improvement=improvement,
            scores_out=scores_out,
            scores_in=scores_in,
            objective=objective,
        )
        result["detailed_reason"] = detailed_reason

    return result


def format_rebalance_plan(
    plan: RebalancePlan,
    all_scores: Dict[str, Dict[str, float]],
    current_codes: Optional[List[str]] = None,
    current_weights: Optional[List[float]] = None,
    include_llm_reason: bool = True,
) -> Dict[str, Any]:
    """
    将单个 RebalancePlan 转换为 dict。

    Returns
    -------
    Dict[str, Any]
        {
            "score_before": ...,
            "score_after": ...,
            "improvement": ...,
            "objective": ...,
            "actions": [format_rebalance_action(...), ...],
            "current_codes": [...],  # 传入时
            "current_weights": [...],  # 传入时
        }
    """
    actions = [
        format_rebalance_action(
            action,
            all_scores,
            plan.score_before,
            plan.score_after,
            plan.improvement,
            plan.objective,
            include_llm_reason,
        )
        for action in plan.actions
    ]

    return {
        "score_before": plan.score_before,
        "score_after": plan.score_after,
        "improvement": plan.improvement,
        "objective": plan.objective,
        "actions": actions,
        "current_codes": current_codes,
        "current_weights": current_weights,
    }


def format_rebalance_plans(
    plans: List[RebalancePlan],
    all_scores: Dict[str, Dict[str, float]],
    current_codes: Optional[List[str]] = None,
    current_weights: Optional[List[float]] = None,
    include_llm_reason: bool = True,
) -> List[Dict[str, Any]]:
    """
    将多个 RebalancePlan 转换为 dict 列表。

    Parameters
    ----------
    plans : List[RebalancePlan]
        调仓方案列表。
    all_scores : Dict[str, Dict[str, float]]
        所有股票的五维评分映射。
    current_codes, current_weights : Optional
        当前组合信息，可选。
    include_llm_reason : bool
        是否调用 LLM 生成详细原因。

    Returns
    -------
    List[Dict[str, Any]]
        格式化后的调仓方案列表。
    """
    return [
        format_rebalance_plan(
            plan, all_scores, current_codes, current_weights, include_llm_reason
        )
        for plan in plans
    ]
