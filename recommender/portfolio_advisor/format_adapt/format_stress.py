from typing import Any, Dict, List, Optional

from recommender.portfolio_advisor.stress_portfolio.const import (
    DEFAULT_SCENARIO_ID_MAP,
)


def _period_from_dates(start_date: str, end_date: str) -> str:
    """从历史场景起止日期生成 'YYYY-MM~YYYY-MM' 形式的 period。"""
    start = start_date[:7] if start_date else ""
    end = end_date[:7] if end_date else ""
    if start and end:
        return f"{start}~{end}"
    return ""


def _build_scenario_list(
    hist_results: List[Dict[str, Any]],
    scenario_id_map: Optional[Dict[str, Dict[str, str]]] = None,
    selected_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """根据历史压力测试结果构造 scenario_list，并标记默认选中项。"""
    mapping = scenario_id_map or DEFAULT_SCENARIO_ID_MAP
    scenario_list: List[Dict[str, Any]] = []
    for r in hist_results:
        name = r.get("scenario_name", "")
        meta = mapping.get(name, {"id": name, "name": name})
        scenario: Dict[str, Any] = {
            "id": meta.get("id", name),
            "name": meta.get("name", name),
        }
        if selected_id is not None and scenario["id"] == selected_id:
            scenario["is_default"] = True
        scenario_list.append(scenario)
    return scenario_list


def _worst_single_fund_alert(
    result: Dict[str, Any], key: str = "drawdown"
) -> Dict[str, Any]:
    """从逐票明细中找出回撤最大（最负）的标的。"""
    per_asset: List[Dict[str, Any]] = result.get("per_asset", [])
    if not per_asset:
        return {"label": "", "drawdown": 0.0}

    worst = min(per_asset, key=lambda x: x.get(key, 0.0))
    return {
        "label": str(worst.get("code", "unknown")),
        "drawdown": round(float(worst.get(key, 0.0)), 4),
    }


def format_stress_scenario(
    hist_result: Dict[str, Any],
    hist_results: List[Dict[str, Any]],
    scenario_id_map: Optional[Dict[str, Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """
    将单个历史极端行情压力测试结果转换为前端展示格式。

    Parameters
    ----------
    hist_result : Dict[str, Any]
        history_stress.calculate_historical_scenario_result 返回的字典。
    hist_results : List[Dict[str, Any]]
        全部历史场景结果，用于构造 scenario_list。
    scenario_id_map : Optional[Dict[str, Dict[str, str]]]
        中文场景名 -> {id, name} 的映射表。默认使用 DEFAULT_SCENARIO_ID_MAP。

    Returns
    -------
    Dict[str, Any]
        {
            "scenario": {"id": ..., "name": ..., "period": ...},
            "portfolio_drawdown": ...,
            "benchmark_drawdown": ...,
            "single_fund_alert": {"label": ..., "drawdown": ...},
            "scenario_list": [...]
        }
    """
    mapping = scenario_id_map or DEFAULT_SCENARIO_ID_MAP
    name = hist_result.get("scenario_name", "")
    meta = mapping.get(name, {"id": name, "name": name})
    selected_id = meta.get("id", name)

    portfolio_drawdown = hist_result.get("portfolio_loss_pct", 0.0) / 100
    benchmark_drawdown = hist_result.get("benchmark_drawdown", 0.0)
    start_date = hist_result.get("start_date", "")
    end_date = hist_result.get("end_date", "")

    single_fund_alert = _worst_single_fund_alert(hist_result)
    scenario_list = _build_scenario_list(hist_results, scenario_id_map, selected_id)

    return {
        "scenario": {
            "id": selected_id,
            "name": meta.get("name", name),
            "period": _period_from_dates(start_date, end_date),
        },
        "portfolio_drawdown": round(float(portfolio_drawdown), 4),
        "benchmark_drawdown": round(float(benchmark_drawdown), 4),
        "single_fund_alert": single_fund_alert,
        "scenario_list": scenario_list,
    }


def format_stress_reports(
    hist_results: List[Dict[str, Any]],
    scenario_id_map: Optional[Dict[str, Dict[str, str]]] = None,
) -> List[Dict[str, Any]]:
    """
    将多个历史极端行情压力测试结果批量转换为前端展示格式。

    Parameters
    ----------
    hist_results : List[Dict[str, Any]]
        history_stress.compute_historical_stress 返回的结果列表。
    scenario_id_map : Optional[Dict[str, Dict[str, str]]]
        中文场景名映射表。默认使用 DEFAULT_SCENARIO_ID_MAP。

    Returns
    -------
    List[Dict[str, Any]]
        每个历史场景对应一个展示格式字典。
    """
    return [
        format_stress_scenario(r, hist_results, scenario_id_map)
        for r in hist_results
    ]


def format_macro_scenario(macro_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    将单个宏观情景压力测试结果转换为前端展示格式。

    Parameters
    ----------
    macro_result : Dict[str, Any]
        scenario_stress.compute_scenario_stress 返回的字典。

    Returns
    -------
    Dict[str, Any]
        {
            "scenario": {"id": ..., "name": ...},
            "portfolio_drawdown": ...,
            "single_fund_alert": {"label": ..., "drawdown": ...},
            "affected_stocks": [...],
            "warnings": [...]
        }
    """
    name = macro_result.get("scenario_name", "")
    portfolio_drawdown = macro_result.get("portfolio_loss_pct", 0.0) / 100

    return {
        "scenario": {"id": name, "name": name},
        "portfolio_drawdown": round(float(portfolio_drawdown), 4),
        "single_fund_alert": _worst_single_fund_alert(
            macro_result, key="stress_return"
        ),
        "affected_stocks": macro_result.get("affected_stocks", []),
        "warnings": macro_result.get("warnings", []),
    }


def format_macro_reports(macro_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    将多个宏观情景压力测试结果批量转换为前端展示格式。

    Parameters
    ----------
    macro_results : List[Dict[str, Any]]
        scenario_stress.compute_scenario_stress 返回的结果列表。

    Returns
    -------
    List[Dict[str, Any]]
        每个宏观情景对应一个展示格式字典。
    """
    return [format_macro_scenario(r) for r in macro_results]


def format_sector_scenario(sector_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    将单个板块压力测试结果转换为前端展示格式。

    Parameters
    ----------
    sector_result : Dict[str, Any]
        sector_stress.compute_sector_stress 返回的字典。

    Returns
    -------
    Dict[str, Any]
        {
            "scenario": {"id": ..., "name": ...},
            "portfolio_drawdown": ...,
            "sector": ...,
            "sector_callback_pct": ...,
            "beta": ...,
            "single_fund_alert": {"label": ..., "drawdown": ...},
            "affected_stocks": [...],
            "warnings": [...]
        }
    """
    name = sector_result.get("scenario", "")
    portfolio_drawdown = sector_result.get("portfolio_loss_pct", 0.0) / 100

    return {
        "scenario": {"id": name, "name": name},
        "portfolio_drawdown": round(float(portfolio_drawdown), 4),
        "sector": sector_result.get("sector", ""),
        "sector_callback_pct": sector_result.get("sector_callback_pct", 0.0),
        "beta": sector_result.get("beta", 0.0),
        "single_fund_alert": _worst_single_fund_alert(
            sector_result, key="stress_return"
        ),
        "affected_stocks": sector_result.get("affected_stocks", []),
        "warnings": sector_result.get("warnings", []),
    }


def format_sector_reports(sector_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    将多个板块压力测试结果批量转换为前端展示格式。

    Parameters
    ----------
    sector_results : List[Dict[str, Any]]
        sector_stress.compute_sector_stress 返回的结果列表。

    Returns
    -------
    List[Dict[str, Any]]
        每个板块情景对应一个展示格式字典。
    """
    return [format_sector_scenario(r) for r in sector_results]


def format_all_stress_reports(
    hist_results: List[Dict[str, Any]],
    macro_results: List[Dict[str, Any]],
    sector_results: List[Dict[str, Any]],
    scenario_id_map: Optional[Dict[str, Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """
    将三类压力测试结果统一格式化为前端展示格式。

    Parameters
    ----------
    hist_results : List[Dict[str, Any]]
        历史极端行情压力测试结果列表。
    macro_results : List[Dict[str, Any]]
        宏观情景压力测试结果列表。
    sector_results : List[Dict[str, Any]]
        板块压力测试结果列表。
    scenario_id_map : Optional[Dict[str, Dict[str, str]]]
        中文场景名 -> {id, name} 的映射表。默认使用 DEFAULT_SCENARIO_ID_MAP。

    Returns
    -------
    Dict[str, Any]
        {
            "stress": {
                "title": "历史极端行情压力测试",
                "scenarios": [...],
            },
            "macro": {
                "title": "宏观情景压力测试",
                "scenarios": [...],
            },
            "sector": {
                "title": "板块压力测试",
                "scenarios": [...],
            },
        }
    """
    return {
        "stress": {
            "title": "历史极端行情压力测试",
            "scenarios": format_stress_reports(hist_results, scenario_id_map),
        },
        "macro": {
            "title": "宏观情景压力测试",
            "scenarios": format_macro_reports(macro_results),
        },
        "sector": {
            "title": "板块压力测试",
            "scenarios": format_sector_reports(sector_results),
        },
    }
