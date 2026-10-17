"""
工具：
- portfolio_diagnosis     —— 组合五维评分（纯计算，零 LLM 调用）。
- single_stock_diagnosis  —— 单股五维预计算结果查询（读 p_advisor_cal_dimensions，零重算零 LLM）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

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


def _find_cal_dimension(code: str) -> Optional[Dict[str, Any]]:
    """
    从 p_advisor_cal_dimensions（get_all_cal_dimension）中按多格式代码匹配单股记录。

    入参支持 baostock 风格（sz.000001）或纯数字代码；内部通过
    data_source._symbol_candidates 生成候选格式，与记录的 code / full_symbol 取交集匹配。
    未命中或数据源不可用时返回 None。
    """
    try:
        from app.core.db import get_all_cal_dimension

        records = get_all_cal_dimension()
    except Exception:
        return None

    # get_all_cal_dimension 在空集合/异常时可能返回非 list，统一兜底
    if not isinstance(records, list) or not records:
        return None

    candidates = set(data_source._symbol_candidates(code))
    candidates.add(code.strip())
    for record in records:
        if not isinstance(record, dict):
            continue
        record_codes = {
            str(record.get("code", "")).strip(),
            str(record.get("full_symbol", "")).strip(),
        }
        record_codes.discard("")
        if record_codes & candidates:
            return record
    return None


def single_stock_diagnosis(code: str) -> str:
    """
    查询单只股票的预计算五维诊断结果（数据源：MongoDB p_advisor_cal_dimensions）。

    与 portfolio_diagnosis 不同，本工具不拉行情、不重算、不调用 LLM，
    直接返回离线打分（compute_stock_dimensions）已落库的单股五维得分
    与综合健康分，供上层 AI 生成人类可读的诊断结论。

    参数
    ----
    code : str
        股票代码，支持 baostock 风格（sh.600000 / sz.000001 / hk.00700）或纯数字代码。

    返回
    ----
    str
        JSON 字符串，结构：{status, tool, data, warnings, error}。
        data 包含 code / name / full_symbol / industry / market / start_date / end_date、
        五维得分（drawdown_control / portfolio_diversification / position_efficiency /
        return_stability / style_balance）以及 composite_score、geometric_composite_score。
        未在 p_advisor_cal_dimensions 中命中时返回 status=error。
    """
    tool = "single_stock_diagnosis"
    try:
        if code is None or not str(code).strip():
            raise ValueError("股票代码不能为空")
        code = str(code).strip()

        record = _find_cal_dimension(code)
        if record is None:
            raise ValueError(
                f"未找到 {code} 的单股五维预计算结果，"
                "请确认该标的已由离线打分写入 p_advisor_cal_dimensions"
            )

        data = {
            "code": record.get("code", code),
            "name": record.get("name", ""),
            "full_symbol": record.get("full_symbol", ""),
            "industry": record.get("industry", ""),
            "market": record.get("market", ""),
            "start_date": record.get("start_date", ""),
            "end_date": record.get("end_date", ""),
            "drawdown_control": {"score": record.get("drawdown_control")},
            "portfolio_diversification": {"score": record.get("portfolio_diversification")},
            "position_efficiency": {"score": record.get("position_efficiency")},
            "return_stability": {"score": record.get("return_stability")},
            "style_balance": {"score": record.get("style_balance")},
            "composite_score": record.get("composite_score"),
            "geometric_composite_score": record.get("geometric_composite_score"),
        }
        return _common.make_response(tool, data)
    except ValueError as e:
        return _common.error_response(tool, str(e))
    except Exception as e:
        return _common.error_response(tool, f"单股五维结果查询失败: {e}")
