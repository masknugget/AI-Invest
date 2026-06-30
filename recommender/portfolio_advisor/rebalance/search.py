"""
组合搜索。

在受限搜索空间内枚举所有合法替换方案，并评估其目标得分提升。
"""

import itertools
import multiprocessing
from typing import List, Optional, Tuple

from recommender.portfolio_advisor.rebalance.constraints import count_overlap_days
from recommender.portfolio_advisor.rebalance.plan_builder import build_replacement_portfolio, make_actions
from recommender.portfolio_advisor.rebalance.scoring import evaluate_portfolio
from recommender.portfolio_advisor.rebalance.types import CandidatePool, RebalancePlan, StockCandidate
from recommender.portfolio_advisor.rebalance.weights import WEIGHT_STRATEGIES


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

    # 任务数较少时，进程启动开销可能大于收益，保留串行路径
    use_parallel = len(args_list) >= 4

    if use_parallel:
        # 线上服务器资源有限，默认最多 2 个进程
        n_workers = min(2, multiprocessing.cpu_count(), len(args_list))
        if verbose:
            print(f"使用 {n_workers} 个进程并行评估 {len(args_list)} 个方案...")
        with multiprocessing.Pool(processes=n_workers) as pool:
            results = pool.map(_evaluate_replacement_worker, args_list, chunksize=max(1, len(args_list) // n_workers // 4))
    else:
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
