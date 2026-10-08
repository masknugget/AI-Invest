"""
工具：portfolio_diagnosis —— 组合五维评分（纯计算，零 LLM 调用）。
"""
from __future__ import annotations

from typing import List

from app.services.mcp.tools.portfolio_advice import _common
from app.services.mcp.tools.portfolio_advice import data_source


def portfolio_diagnosis(codes: List[str], weights: List[float]) -> str:
    """
    计算投资组合五维诊断评分：回撤控制、组合分散度、仓位效率、收益稳定性、风格平衡，以及综合健康分。

    返回原始指标值与各维度 0-100 得分，供上层 AI 生成人类可读的诊断结论。
    本工具只做计算，不生成任何分析文本。

    参数
    ----
    codes : List[str]
        股票代码列表，支持 baostock 风格（sh.600000 / sz.000001 / hk.00700）。
    weights : List[float]
        各标的权重，长度须与 codes 一致；允许总和不为 1，内部自动归一化。

    返回
    ----
    str
        JSON 字符串，结构：{status, tool, data, warnings, error}。
        data 包含各维度原始指标、score(0-100)、composite_score、
        geometric_composite_score、dimension_weights。
        行情数据依次尝试 MongoDB / akshare / yfinance。
    """
    tool = "portfolio_diagnosis"
    try:
        codes, weights = _common.validate_portfolio(codes, weights)
        dfs_map = data_source.fetch_quotes(codes)
        dfs = [dfs_map[c] for c in codes]

        result = _common.get_dimension_run().compute_portfolio_dimensions(dfs, weights)

        data = {
            "codes": codes,
            "weights": weights,
            "drawdown_control": {
                "max_drawdown": result.drawdown_control.mdd,
                "score": result.drawdown_control.score,
            },
            "portfolio_diversification": {
                "enb_weight_based": result.portfolio_diversification.enb_weight_based,
                "enb_risk_based": result.portfolio_diversification.enb_risk_based,
                "score": result.portfolio_diversification.score,
            },
            "position_efficiency": {
                "sharpe_ratio": result.position_efficiency.sharpe_ratio,
                "score": result.position_efficiency.score,
            },
            "return_stability": {
                "annualized_volatility": result.return_stability.annualized_volatility,
                "score": result.return_stability.score,
            },
            "style_balance": {
                "style_hhi": result.style_balance.style_hhi,
                "effective_style_num": result.style_balance.effective_style_num,
                "score": result.style_balance.score,
            },
            "composite_score": result.composite_score,
            "geometric_composite_score": result.geometric_composite_score,
            "dimension_weights": dict(result.dimension_weights),
        }
        return _common.make_response(tool, data)
    except ValueError as e:
        return _common.error_response(tool, str(e))
    except Exception as e:
        return _common.error_response(tool, f"五维评分计算失败: {e}")
