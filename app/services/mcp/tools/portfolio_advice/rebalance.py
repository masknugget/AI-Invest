"""
工具：portfolio_rebalance_suggestion —— 调仓建议（纯计算，零 LLM 调用）。

依赖预计算文件 stock_dimension_scores.jsonl（候选池离线五维打分产物）。
"""
from __future__ import annotations

from typing import List

from app.services.mcp.tools.portfolio_advice import _common


def portfolio_rebalance_suggestion(
    codes: List[str],
    weights: List[float],
    objective: str = "composite_score",
    max_actions: int = 1,
    top_k: int = 3,
) -> str:
    """
    基于候选池预计算五维得分，生成调仓建议（调入/调出组合，调仓前后得分对比）。

    本工具不含 LLM 调用，只返回结构化方案数据（score_before / score_after /
    improvement / actions / 调仓前后各维度得分），调仓理由由上层 AI 依据这些数据生成。

    参数
    ----
    codes : List[str]
        当前组合标的代码，须与预计算分数文件中的代码格式一致（如 sh.600000）。
    weights : List[float]
        当前组合权重，长度须与 codes 一致；允许总和不为 1，内部自动归一化。
    objective : str
        优化目标："composite_score"（算术加权综合分，默认）/
        "geometric_composite_score"（几何加权综合分）/ "min_dimension_score" /
        "dimension:<维度名>"。
    max_actions : int
        单次最多同时替换几只股票，取值 [1, 3]，默认 1。
    top_k : int
        返回前 K 个最优方案，默认 3。

    返回
    ----
    str
        JSON 字符串，结构：{status, tool, data, warnings, error}。
        status=error 时 error 携带可读中文说明（如分数文件缺失、
        当前组合股票缺少维度得分）。分数文件超过 7 天未更新时在 warnings 中提示。
    """
    tool = "portfolio_rebalance_suggestion"
    try:
        codes, weights = _common.validate_portfolio(codes, weights)

        scores_path, warnings = _common.check_scores_file()

        from recommender.portfolio_advisor.rebalance import suggest_rebalance

        plans = suggest_rebalance(
            current_codes=codes,
            current_weights=weights,
            scores_path=str(scores_path),
            objective=objective,
            max_actions=max_actions,
            top_k=top_k,
        )

        data = {
            "codes": codes,
            "weights": weights,
            "objective": objective,
            "scores_file": _common.scores_file_meta(),
            "plan_count": len(plans),
            "plans": [p.to_dict() for p in plans],
        }
        if not plans:
            warnings.append(
                "未找到满足条件的调仓方案（可能当前组合在该目标函数下已较优，"
                "或候选池不足），可尝试放宽 objective / max_actions 后重试"
            )
        return _common.make_response(tool, data, warnings=warnings)
    except ValueError as e:
        return _common.error_response(tool, str(e))
    except Exception as e:
        return _common.error_response(tool, f"调仓建议计算失败: {e}")
