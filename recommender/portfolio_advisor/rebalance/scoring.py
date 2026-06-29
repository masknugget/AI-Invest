"""
目标函数评分。

将 PortfolioDimensions 映射到各种优化目标得分。
"""

from typing import Set

from research.portfolio_advisor.dimension.run import PortfolioDimensions, compute_portfolio_dimensions


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
