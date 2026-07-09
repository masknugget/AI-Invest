"""
组合搜索。

在受限搜索空间内枚举所有合法替换方案，并评估其目标得分提升。
"""

import itertools
from typing import Dict, List, Optional, Tuple

from recommender.portfolio_advisor.rebalance.constraints import count_overlap_days
from recommender.portfolio_advisor.rebalance.plan_builder import build_replacement_portfolio, make_actions
from recommender.portfolio_advisor.rebalance.scoring import evaluate_portfolio, evaluate_portfolio_from_scores
from recommender.portfolio_advisor.rebalance.types import CandidatePool, RebalancePlan, StockCandidate
from recommender.portfolio_advisor.rebalance.weights import WEIGHT_STRATEGIES, redistribute_weights


def iter_replacement_candidates(
    n_current: int,
    n_candidates: int,
    max_actions: int,
):
    """
    枚举所有合法的对称替换组合。

    Yields
    ------
    Tuple[Tuple[int, ...], Tuple[StockCandidate, ...]]
        (调出索引元组, 调入候选元组)。
    """
    for k in range(1, max_actions + 1):
        if k > n_current or k > n_candidates:
            continue
        for out_indices in itertools.combinations(range(n_current), k):
            for in_candidates in itertools.combinations(range(n_candidates), k):
                yield out_indices, in_candidates


def _evaluate_replacement_worker(args) -> Tuple[Optional[RebalancePlan], List[str]]:
    """
    多进程工作函数：评估单个替换组合。

    返回 (RebalancePlan 或 None, 需打印的 verbose 消息列表)。
    """
    (
        current_codes,
        current_weights,
        current_dfs,
        out_indices,
        in_candidate_codes,
        in_candidate_dfs,
        score_current,
        portfolio_current,
        objective,
        min_improvement,
        weight_strategy,
        fixed_new_weight,
        min_overlap_days,
        verbose,
    ) = args

    in_candidates = tuple(
        StockCandidate(code=code, df=df, dimension_scores={})
        for code, df in zip(in_candidate_codes, in_candidate_dfs)
    )

    messages: List[str] = []
    try:
        new_codes, new_weights, new_dfs, _ = build_replacement_portfolio(
            current_codes,
            current_weights,
            current_dfs,
            out_indices,
            in_candidates,
            weight_strategy,
            fixed_new_weight,
        )

        if min_overlap_days is not None and count_overlap_days(new_dfs) < min_overlap_days:
            if verbose:
                out_codes = [current_codes[i] for i in out_indices]
                in_codes = [c.code for c in in_candidates]
                messages.append(f"方案 {out_codes} -> {in_codes} 重叠交易日不足，跳过")
            return None, messages

        score_new, portfolio_new = evaluate_portfolio(
            new_codes, new_weights, new_dfs, objective
        )
        improvement = score_new - score_current

        if improvement < min_improvement:
            return None, messages

        actions = make_actions(
            current_codes,
            out_indices,
            in_candidates,
            new_weights,
            weight_strategy,
            improvement,
        )

        plan = RebalancePlan(
            actions=actions,
            portfolio_before=portfolio_current,
            portfolio_after=portfolio_new,
            score_before=score_current,
            score_after=score_new,
            improvement=improvement,
            objective=objective,
        )
        return plan, messages

    except Exception as exc:  # noqa: BLE001
        if verbose:
            out_codes = [current_codes[i] for i in out_indices]
            in_codes = [c.code for c in in_candidates]
            messages.append(f"评估方案 {out_codes} -> {in_codes} 失败: {exc}")
        return None, messages


def search_rebalance_plans(
    current_codes: List[str],
    current_weights: List[float],
    current_dfs,
    candidate_pool: CandidatePool,
    score_current: float,
    portfolio_current,
    objective: str,
    max_actions: int,
    min_improvement: float,
    weight_strategy: str,
    fixed_new_weight: float,
    min_overlap_days: Optional[int] = None,
    verbose: bool = False,
) -> List[RebalancePlan]:
    """
    搜索并返回所有满足约束的 RebalancePlan，按 improvement 降序排列。

    不对结果截断 top_k，由调用方决定返回数量。
    当候选组合较多时，使用多进程并行评估以加速搜索。
    """
    if weight_strategy not in WEIGHT_STRATEGIES:
        raise ValueError(f"不支持的权重策略: {weight_strategy}，可选: {WEIGHT_STRATEGIES}")

    candidates = list(candidate_pool.candidates)
    n_current = len(current_codes)
    n_candidates = len(candidates)

    # 构造任务参数列表，仅传递必要数据，避免重复序列化整个候选池
    args_list: List[Tuple] = []
    for out_indices, in_candidate_indices in iter_replacement_candidates(
        n_current, n_candidates, max_actions
    ):
        in_candidate_codes = tuple(candidates[i].code for i in in_candidate_indices)
        in_candidate_dfs = tuple(candidates[i].df for i in in_candidate_indices)
        args_list.append(
            (
                current_codes,
                current_weights,
                current_dfs,
                out_indices,
                in_candidate_codes,
                in_candidate_dfs,
                score_current,
                portfolio_current,
                objective,
                min_improvement,
                weight_strategy,
                fixed_new_weight,
                min_overlap_days,
                verbose,
            )
        )

    plans: List[RebalancePlan] = []
    messages: List[str] = []

    # 串行评估所有方案，避免多进程序列化与启动开销
    if verbose:
        print(f"串行评估 {len(args_list)} 个方案...")
    results = [_evaluate_replacement_worker(args) for args in args_list]

    for plan, msgs in results:
        messages.extend(msgs)
        if plan is not None:
            plans.append(plan)

    if verbose:
        for msg in messages:
            print(msg)

    plans.sort(key=lambda p: p.improvement, reverse=True)
    return plans


def _evaluate_replacement_worker_by_scores(args) -> Tuple[Optional[RebalancePlan], List[str]]:
    """
    基于预计算维度得分评估单个替换组合。

    返回 (RebalancePlan 或 None, 需打印的 verbose 消息列表)。
    """
    (
        current_codes,
        current_weights,
        current_stock_scores,
        out_indices,
        in_candidate_codes,
        in_candidate_scores,
        score_current,
        portfolio_current,
        objective,
        min_improvement,
        weight_strategy,
        fixed_new_weight,
        verbose,
    ) = args

    messages: List[str] = []
    try:
        out_indices_set = set(out_indices)
        remaining_codes = [c for i, c in enumerate(current_codes) if i not in out_indices_set]
        remaining_weights = [w for i, w in enumerate(current_weights) if i not in out_indices_set]
        remaining_scores = [s for i, s in enumerate(current_stock_scores) if i not in out_indices_set]

        n_new = len(in_candidate_codes)
        total_removed_weight = sum(current_weights[i] for i in out_indices)

        new_codes = remaining_codes + list(in_candidate_codes)
        new_scores = remaining_scores + list(in_candidate_scores)

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

        score_new, portfolio_new = evaluate_portfolio_from_scores(
            new_codes, new_scores, new_weights, objective
        )
        improvement = score_new - score_current

        if improvement < min_improvement:
            return None, messages

        in_candidates = tuple(
            StockCandidate(code=code, df=None, dimension_scores=scores)
            for code, scores in zip(in_candidate_codes, in_candidate_scores)
        )

        actions = make_actions(
            current_codes,
            out_indices,
            in_candidates,
            new_weights,
            weight_strategy,
            improvement,
        )

        plan = RebalancePlan(
            actions=actions,
            portfolio_before=portfolio_current,
            portfolio_after=portfolio_new,
            score_before=score_current,
            score_after=score_new,
            improvement=improvement,
            objective=objective,
        )
        return plan, messages

    except Exception as exc:  # noqa: BLE001
        if verbose:
            out_codes = [current_codes[i] for i in out_indices]
            in_codes = list(in_candidate_codes)
            messages.append(f"评估方案 {out_codes} -> {in_codes} 失败: {exc}")
        return None, messages


def search_rebalance_plans_by_scores(
    current_codes: List[str],
    current_weights: List[float],
    current_stock_scores: List[Dict[str, float]],
    candidate_pool: CandidatePool,
    score_current: float,
    portfolio_current,
    objective: str,
    max_actions: int,
    min_improvement: float,
    weight_strategy: str,
    fixed_new_weight: float,
    verbose: bool = False,
) -> List[RebalancePlan]:
    """
    基于预计算维度得分搜索并返回 RebalancePlan，按 improvement 降序排列。

    不依赖 DataFrame，通过加权聚合个股维度得分近似组合得分。
    不对结果截断 top_k，由调用方决定返回数量。
    """
    if weight_strategy not in WEIGHT_STRATEGIES:
        raise ValueError(f"不支持的权重策略: {weight_strategy}，可选: {WEIGHT_STRATEGIES}")

    candidates = list(candidate_pool.candidates)
    n_current = len(current_codes)
    n_candidates = len(candidates)

    args_list: List[Tuple] = []
    for out_indices, in_candidate_indices in iter_replacement_candidates(
        n_current, n_candidates, max_actions
    ):
        in_candidate_codes = tuple(candidates[i].code for i in in_candidate_indices)
        in_candidate_scores = tuple(candidates[i].dimension_scores for i in in_candidate_indices)
        args_list.append(
            (
                current_codes,
                current_weights,
                current_stock_scores,
                out_indices,
                in_candidate_codes,
                in_candidate_scores,
                score_current,
                portfolio_current,
                objective,
                min_improvement,
                weight_strategy,
                fixed_new_weight,
                verbose,
            )
        )

    plans: List[RebalancePlan] = []
    messages: List[str] = []

    if verbose:
        print(f"串行评估 {len(args_list)} 个方案（基于 dimension_scores）...")
    results = [_evaluate_replacement_worker_by_scores(args) for args in args_list]

    for plan, msgs in results:
        messages.extend(msgs)
        if plan is not None:
            plans.append(plan)

    if verbose:
        for msg in messages:
            print(msg)

    plans.sort(key=lambda p: p.improvement, reverse=True)
    return plans
