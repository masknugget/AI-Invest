from typing import Any, Dict, List, Optional

from datetime import datetime

from recommender.portfolio_advisor.dimension.run import PortfolioDimensions


def format_dimensions(
    result: PortfolioDimensions,
    disclaimer: str = "以上维度评分由 AI 模型生成，仅供参考，不构成投资建议。",
) -> Dict[str, Any]:
    """
    将 compute_portfolio_dimensions 的 PortfolioDimensions 结果转换为
    mock/risk_diagnosis/dimensions.json 对齐格式。

    Parameters
    ----------
    result : PortfolioDimensions
        compute_portfolio_dimensions 的输出。
    disclaimer : str
        底部免责声明。

    Returns
    -------
    Dict[str, Any]
        与 dimensions.json 结构一致的字典。
    """
    dimension_items: List[Dict[str, Any]] = [
        {
            "key": "return_stability",
            "name": "收益稳定性",
            "score": int(round(result.return_stability.score)),
            "weight": 0.20,
            "description": "近一年收益波动较小"
            if result.return_stability.score >= 70
            else "收益波动相对明显",
        },
        {
            "key": "style_balance",
            "name": "风格均衡",
            "score": int(round(result.style_balance.score)),
            "weight": 0.20,
            "description": "成长与价值风格配置较为均衡"
            if result.style_balance.score >= 70
            else "成长与价值风格配置尚不均衡",
        },
        {
            "key": "cost_performance",
            "name": "持仓性价比",
            "score": int(round(result.position_efficiency.score)),
            "weight": 0.20,
            "description": "整体估值处于合理区间"
            if result.position_efficiency.score >= 60
            else "整体估值性价比偏低",
        },
        {
            "key": "drawback_resistance",
            "name": "抗回撤能力",
            "score": int(round(result.drawdown_control.score)),
            "weight": 0.20,
            "description": "最大回撤控制尚可"
            if result.drawdown_control.score >= 60
            else "最大回撤控制有待加强",
        },
        {
            "key": "industry_diversification",
            "name": "行业分散度",
            "score": int(round(result.portfolio_diversification.score)),
            "weight": 0.20,
            "description": "行业配置相对分散"
            if result.portfolio_diversification.score >= 60
            else "行业集中度偏高，存在单一行业依赖",
        },
    ]

    return {
        "dimensions": dimension_items,
        "disclaimer": disclaimer,
    }


def _rating_from_score(score: float) -> Dict[str, str]:
    """根据健康分生成评级信息。"""
    if score >= 80:
        return {"level": "excellent", "label": "优秀", "sub_label": "健康"}
    if score >= 60:
        return {"level": "good", "label": "良好", "sub_label": "亚健康"}
    if score >= 40:
        return {"level": "average", "label": "一般", "sub_label": "需关注"}
    return {"level": "poor", "label": "较差", "sub_label": "高风险"}


def format_report(
    result: PortfolioDimensions,
    comprehensive_str: str,
    update_time: Optional[str] = None,
    disclaimer: str = "以上评分由 AI 模型基于模拟持仓数据生成，仅供参考，不构成投资建议。市场有风险，投资需谨慎。",
) -> Dict[str, Any]:
    """
    将 PortfolioDimensions 与综合评语转换为
    mock/risk_diagnosis/report.json 对齐格式。

    Parameters
    ----------
    result : PortfolioDimensions
        compute_portfolio_dimensions 的输出。
    comprehensive_str : str
        综合评语，对应输出中的 comment。
    update_time : Optional[str]
        报告更新时间。为 None 时使用当前时间。
    disclaimer : str
        底部免责声明。

    Returns
    -------
    Dict[str, Any]
        与 report.json 结构一致的字典。
    """
    health_score = int(round(result.composite_score))

    if update_time is None:
        update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return {
        "health_score": health_score,
        "rating": _rating_from_score(health_score),
        "comment": comprehensive_str,
        "update_time": update_time,
        "disclaimer": disclaimer,
    }


def _infer_severity(summary: str, detail: str) -> str:
    """根据风险描述简单推断严重等级。"""
    text = (summary + detail).lower()
    high_keywords = ["清盘", "爆仓", "巨大", "致命", "极高", "严重", "过度集中", "崩塌"]
    low_keywords = ["轻微", "略有", "稍高", "偏弱"]
    if any(k in text for k in high_keywords):
        return "high"
    if any(k in text for k in low_keywords):
        return "low"
    return "medium"


def _severity_label(severity: str) -> str:
    """严重等级 -> 中文标签。"""
    return {"high": "高风险", "medium": "中风险", "low": "低风险"}.get(severity, "中风险")


def _severity_icon(severity: str) -> str:
    """严重等级 -> 图标标识。"""
    return {
        "high": "warning_high",
        "medium": "warning_medium",
        "low": "warning_low",
    }.get(severity, "warning_medium")


def format_risk_alerts(
    risks: List[Dict[str, str]],
    disclaimer: str = "以上风险提示由 AI 模型生成，仅供参考，不构成投资建议。",
) -> Dict[str, Any]:
    """
    将 parse_risks 返回的 List[Dict[str, str]] 转换为
    mock/risk_diagnosis/risk_alerts.json 对齐格式。

    源数据仅包含 summary/detail，因此输出中只保留能填充的字段：
    id / severity / severity_label / type_name / title / description / icon。
    源中不存在的 metrics / suggestion / type 等字段直接舍弃。

    Parameters
    ----------
    risks : List[Dict[str, str]]
        parse_risks 的输出，每个元素包含 summary 和 detail。
    disclaimer : str
        底部免责声明。

    Returns
    -------
    Dict[str, Any]
        与 risk_alerts.json 结构一致的字典。
    """
    alerts: List[Dict[str, Any]] = []

    for idx, risk in enumerate(risks):
        summary = risk.get("summary", "")
        detail = risk.get("detail", "")
        severity = _infer_severity(summary, detail)

        alert = {
            "id": f"risk_{idx + 1:03d}",
            "severity": severity,
            "severity_label": _severity_label(severity),
            "type_name": summary,
            "title": summary,
            "description": detail,
            "icon": _severity_icon(severity),
        }
        alerts.append(alert)

    return {
        "total_count": len(alerts),
        "alerts": alerts,
        "disclaimer": disclaimer,
    }


def format_advisor_result(
    dimensions: Dict[str, Any],
    risk_report: Dict[str, Any],
    risk_alert: Dict[str, Any],
    industry_distribution: Dict[str, Any],
) -> Dict[str, Any]:
    """
    将 portfolio advisor 的多个子结果整合为统一格式。

    Parameters
    ----------
    dimensions : Dict[str, Any]
        format_dimensions 输出。
    risk_report : Dict[str, Any]
        format_report 输出。
    risk_alert : Dict[str, Any]
        format_risk_alerts 输出。
    industry_distribution : Dict[str, Any]
        行业分布字典，例如 {"消费/白酒": 0.4, ...}。
    stress_test : Optional[Dict[str, Any]]
        压力测试结果。为 None 时使用空字典。

    Returns
    -------
    Dict[str, Any]
        整合后的 advisor 结果字典。
    """
    return {
        "dimensions": dimensions,
        "risk_report": risk_report,
        "risk_alert": risk_alert,
        "industry_distribution": industry_distribution,
    }
