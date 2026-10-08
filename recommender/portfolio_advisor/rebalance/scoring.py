"""
目标函数评分。

将 PortfolioDimensions 映射到各种优化目标得分。
"""

from typing import Dict, List, Optional, Set

from recommender.portfolio_advisor.dimension.run import (
    DEFAULT_DIMENSION_WEIGHTS,
    GEOMETRIC_DIMENSION_WEIGHTS,
    DrawdownControl,
    PortfolioDiversification,
    PortfolioDimensions,
    PositionEfficiency,
    ReturnStability,
    StyleBalance,
    compute_geometric_composite_score,
    compute_portfolio_dimensions,
)

# one.py 持久化的可选原始指标，聚合后填充进合成 PortfolioDimensions，
# 避免下游展示"预计回撤 = 0"之类的无意义数值（旧版得分文件无这些字段）
METRIC_NAMES: Set[str] = {
    "mdd",
    "sharpe_ratio",
    "annualized_volatility",
    "enb_weight_based",
    "style_hhi",
}


OBJECTIVES: Set[str] = {
    "composite_score",
    "geometric_composite_score",
    "min_dimension_score",
}


def extract_objective_score(result: PortfolioDimensions, objective: str) -> float:
    """从 PortfolioDimensions 中提取指定目标得分。"""
    if objective == "composite_score":
        return float(result.composite_score)
    if objective == "geometric_composite_score":
        return float(result.geometric_composite_score)
    if objective == "min_dimension_score":
        return min(result.to_score_dict().values())
    if objective.startswith("dimension:"):
        dim_name = objective.split(":", 1)[1]
        score_dict = result.to_score_dict()
        if dim_name not in score_dict:
            raise ValueError(f"未知维度: {dim_name}，可选: {list(score_dict.keys())}")
        return float(score_dict[dim_name])

    raise ValueError(
        f"未知优化目标: {objective}，可选: {OBJECTIVES} 或 'dimension:<name>'"
    )


def evaluate_portfolio(
    codes,
    weights,
    dfs,
    objective: str = "geometric_composite_score",
):
    """
    计算指定目标函数下的组合得分与完整诊断结果。

    Parameters
    ----------
    codes : List[str]
        组合标的代码（仅用于错误信息）。
    weights : List[float]
        组合权重。
    dfs : List[pd.DataFrame]
        组合行情数据。
    objective : str, default "geometric_composite_score"
        优化目标。

    Returns
    -------
    Tuple[float, PortfolioDimensions]
        (目标得分, 完整五维诊断结果)。
    """
    result = compute_portfolio_dimensions(dfs, weights)
    score = extract_objective_score(result, objective)
    return score, result


def _aggregate_dimension_scores(
    dimension_scores_list: List[Dict[str, float]],
    weights: List[float],
) -> Dict[str, float]:
    """按权重聚合多只股票的五维得分为组合维度得分。"""
    if len(dimension_scores_list) != len(weights):
        raise ValueError("dimension_scores_list 与 weights 长度必须一致")

    total_weight = sum(weights)
    if total_weight <= 0:
        raise ValueError("权重总和必须为正")

    all_dims = set()
    for scores in dimension_scores_list:
        all_dims.update(scores.keys())
    # 原始指标键不参与维度得分聚合
    all_dims -= METRIC_NAMES

    result = {}
    for dim in all_dims:
        weighted_sum = sum(
            scores.get(dim, 0.0) * w for scores, w in zip(dimension_scores_list, weights)
        )
        result[dim] = weighted_sum / total_weight
    return result


def _aggregate_metrics(
    dimension_scores_list: List[Dict[str, float]],
    weights: List[float],
) -> Dict[str, float]:
    """按权重聚合各股票的原始指标（mdd / sharpe 等）。

    近似说明：组合层面的真实指标是路径依赖的（如组合 MDD 不等于个股 MDD
    的加权平均），此处加权平均仅用于展示参考，严格计算需行情数据重算。
    无任何股票带指标字段时返回空字典。
    """
    total_weight = sum(weights)
    aggregated: Dict[str, float] = {}
    for metric in METRIC_NAMES:
        pairs = [
            (scores[metric], w)
            for scores, w in zip(dimension_scores_list, weights)
            if metric in scores
        ]
        if not pairs:
            continue
        covered = sum(w for _, w in pairs)
        aggregated[metric] = sum(v * w for v, w in pairs) / covered if covered > 0 else 0.0
    return aggregated


def make_portfolio_dimensions_from_scores(
    scores: Dict[str, float],
    dimension_weights=None,
    geometric_weights=None,
    metrics: Optional[Dict[str, float]] = None,
) -> PortfolioDimensions:
    """从维度得分字典构造合成 PortfolioDimensions。

    指标值（mdd / sharpe 等）优先取 metrics 参数（个股指标加权聚合结果）；
    未提供时置 0.0，仅保留得分。原始指标需 one.py 生成的得分文件携带，
    旧版文件无指标字段时行为与此前一致。
    """
    if dimension_weights is None:
        dimension_weights = DEFAULT_DIMENSION_WEIGHTS
    if geometric_weights is None:
        geometric_weights = GEOMETRIC_DIMENSION_WEIGHTS
    if metrics is None:
        metrics = {}

    # 确保所有维度都有值，缺失补 0
    complete_scores = {dim: scores.get(dim, 0.0) for dim in dimension_weights}
    complete_scores.update(
        {dim: scores.get(dim, 0.0) for dim in geometric_weights if dim not in complete_scores}
    )

    composite_score = sum(
        dimension_weights[dim] * complete_scores[dim] for dim in dimension_weights
    )
    geometric_composite_score = compute_geometric_composite_score(complete_scores, geometric_weights)

    return PortfolioDimensions(
        drawdown_control=DrawdownControl(
            mdd=float(metrics.get("mdd", 0.0)),
            score=complete_scores.get("drawdown_control", 0.0),
        ),
        portfolio_diversification=PortfolioDiversification(
            enb_weight_based=float(metrics.get("enb_weight_based", 0.0)),
            enb_risk_based=0.0,  # 个股级不持久化风险 ENB，组合值需行情重算
            score=complete_scores.get("portfolio_diversification", 0.0),
        ),
        position_efficiency=PositionEfficiency(
            sharpe_ratio=float(metrics.get("sharpe_ratio", 0.0)),
            score=complete_scores.get("position_efficiency", 0.0),
        ),
        return_stability=ReturnStability(
            annualized_volatility=float(metrics.get("annualized_volatility", 0.0)),
            score=complete_scores.get("return_stability", 0.0),
        ),
        style_balance=StyleBalance(
            style_hhi=float(metrics.get("style_hhi", 0.0)),
            effective_style_num=0.0,
            score=complete_scores.get("style_balance", 0.0),
        ),
        composite_score=composite_score,
        geometric_composite_score=geometric_composite_score,
        dimension_weights=dict(dimension_weights),
    )


def evaluate_portfolio_from_scores(
    codes: List[str],
    dimension_scores_list: List[Dict[str, float]],
    weights: List[float],
    objective: str = "geometric_composite_score",
):
    """
    基于预计算的个股维度得分，计算组合目标得分与合成 PortfolioDimensions。

    Parameters
    ----------
    codes : List[str]
        组合标的代码（仅用于错误信息）。
    dimension_scores_list : List[Dict[str, float]]
        每只股票的五维得分。
    weights : List[float]
        各股票权重。
    objective : str, default "geometric_composite_score"
        优化目标。

    Returns
    -------
    Tuple[float, PortfolioDimensions]
        (目标得分, 合成 PortfolioDimensions)。
    """
    aggregated_scores = _aggregate_dimension_scores(dimension_scores_list, weights)
    aggregated_metrics = _aggregate_metrics(dimension_scores_list, weights)
    portfolio = make_portfolio_dimensions_from_scores(aggregated_scores, metrics=aggregated_metrics)
    score = extract_objective_score(portfolio, objective)
    return score, portfolio
