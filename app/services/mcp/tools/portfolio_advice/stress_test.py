"""
工具：portfolio_stress_test —— 组合压力测试（纯计算，零 LLM 调用）。
"""
from __future__ import annotations

from typing import Dict, List, Optional

from app.services.mcp.tools.portfolio_advice import _common
from app.services.mcp.tools.portfolio_advice import data_source

_VALID_SCENARIO_TYPES = ("history", "scenario", "sector")


def _run_history_stress(codes, weights, scenario_names, warnings) -> List[Dict]:
    from recommender.portfolio_advisor.stress_portfolio.history_stress import (
        compute_historical_stress,
        list_historical_scenario_names,
    )

    dfs_map = data_source.fetch_quotes(codes)
    portfolio = _common.build_portfolio_arg(codes, weights)
    results = compute_historical_stress(portfolio, dfs_map, scenario_ids=scenario_names)
    if not results:
        warnings.append(
            "历史压力测试无结果，可用历史场景: " + ", ".join(list_historical_scenario_names())
        )
    return results


def _run_scenario_stress(codes, weights, scenario_names, warnings) -> List[Dict]:
    from recommender.portfolio_advisor.stress_portfolio.scenario_stress import (
        compute_scenario_stress,
        list_scenario_names,
    )

    portfolio = _common.build_portfolio_arg(codes, weights)
    names = scenario_names or list_scenario_names()
    results = []
    for name in names:
        try:
            results.append(
                compute_scenario_stress(
                    portfolio, name, industry_lookup=data_source.industry_lookup
                )
            )
        except ValueError as e:
            warnings.append(f"宏观情景「{name}」计算跳过: {e}")
    return results


def _run_sector_stress(codes, weights, scenario_names, warnings) -> List[Dict]:
    from recommender.portfolio_advisor.stress_portfolio.sector_stress import (
        compute_sector_stress,
        list_sector_names,
    )

    portfolio = _common.build_portfolio_arg(codes, weights)
    sectors = scenario_names or list_sector_names()
    results = []
    for sector in sectors:
        try:
            results.append(
                compute_sector_stress(
                    portfolio, sector=sector, industry_lookup=data_source.industry_lookup
                )
            )
        except ValueError as e:
            warnings.append(f"行业情景「{sector}」计算跳过: {e}")
    return results


_STRESS_DISPATCH = {
    "history": _run_history_stress,
    "scenario": _run_scenario_stress,
    "sector": _run_sector_stress,
}


def portfolio_stress_test(
    codes: List[str],
    weights: List[float],
    scenario_type: str = "history",
    scenario_names: Optional[List[str]] = None,
) -> str:
    """
    对投资组合做压力测试，估算各类极端情景下的组合损失。

    本工具只做计算，返回结构化损失指标；情景解读文本由上层 AI 生成。

    参数
    ----
    codes : List[str]
        股票代码列表，支持 baostock 风格（sh.600000 / sz.000001 / hk.00700）。
    weights : List[float]
        各标的权重，长度须与 codes 一致；允许总和不为 1，内部自动归一化。
    scenario_type : str
        情景类型："history"（历史极端行情，需要行情数据，默认）/
        "scenario"（预定义宏观情景）/ "sector"（行业回调情景）。
    scenario_names : Optional[List[str]]
        具体情景名称列表；为空时该类型下全部情景均计算。
        可用名称可先以空列表调用一次，从返回的 warnings 中获取。

    返回
    ----
    str
        JSON 字符串，结构：{status, tool, data, warnings, error}。
        data 为各情景的损失结果列表（含 portfolio_loss_pct / per_asset / warnings 等）。
        个别情景计算失败不影响其他情景，失败信息写入 warnings。
    """
    tool = "portfolio_stress_test"
    try:
        codes, weights = _common.validate_portfolio(codes, weights)
        scenario_type = (scenario_type or "history").strip().lower()
        if scenario_type not in _VALID_SCENARIO_TYPES:
            raise ValueError(
                f"不支持的情景类型: {scenario_type}，可选: {list(_VALID_SCENARIO_TYPES)}"
            )

        warnings: List[str] = []
        results = _STRESS_DISPATCH[scenario_type](codes, weights, scenario_names, warnings)

        status = "success" if results else ("partial" if warnings else "success")
        data = {
            "scenario_type": scenario_type,
            "codes": codes,
            "weights": weights,
            "results": results,
        }
        return _common.make_response(tool, data, status=status, warnings=warnings)
    except ValueError as e:
        return _common.error_response(tool, str(e))
    except Exception as e:
        return _common.error_response(tool, f"压力测试计算失败: {e}")
