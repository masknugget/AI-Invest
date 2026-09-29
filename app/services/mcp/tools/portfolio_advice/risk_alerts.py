"""
工具：portfolio_risk_alerts —— 行业分布 + 规则化风险指标（纯计算，零 LLM 调用）。
"""
from __future__ import annotations

from typing import Dict, List

from app.services.mcp.tools.portfolio_advice import _common

# HHI 集中度阈值
_HHI_HIGH = 0.5
_HHI_MEDIUM = 0.25
# 单一标权重阈值
_SINGLE_WEIGHT_HIGH = 0.4


def _rule_based_risks(
    industry_dist: Dict[str, float],
    hhi: float,
    weights_by_code: Dict[str, float],
) -> List[Dict[str, str]]:
    """基于行业集中度与个股权重的规则化风险项。"""
    risks: List[Dict[str, str]] = []

    top_industry = max(industry_dist, key=industry_dist.get) if industry_dist else None
    if hhi >= _HHI_HIGH:
        risks.append({
            "summary": "行业集中度过高",
            "detail": (
                f"行业分布赫芬达尔指数 HHI={hhi:.2f}（>= {_HHI_HIGH}），"
                f"第一大行业「{top_industry}」占比 {industry_dist.get(top_industry, 0):.1%}，"
                "组合对单一行业依赖显著，行业性风险事件冲击大。"
            ),
        })
    elif hhi >= _HHI_MEDIUM:
        risks.append({
            "summary": "行业集中度偏高",
            "detail": (
                f"行业分布赫芬达尔指数 HHI={hhi:.2f}（>= {_HHI_MEDIUM}），"
                f"第一大行业「{top_industry}」占比 {industry_dist.get(top_industry, 0):.1%}，"
                "建议关注行业分散度。"
            ),
        })

    for code, w in weights_by_code.items():
        if w >= _SINGLE_WEIGHT_HIGH:
            risks.append({
                "summary": "单一标的权重过高",
                "detail": (
                    f"{code} 权重 {w:.1%}（>= {_SINGLE_WEIGHT_HIGH:.0%}），"
                    "个股特有风险对组合影响较大。"
                ),
            })

    if "未知行业" in industry_dist:
        risks.append({
            "summary": "部分标的信息缺失",
            "detail": (
                f"{industry_dist['未知行业']:.1%} 的权重无法识别行业，"
                "相关风险未被完整评估。"
            ),
        })

    if not risks:
        risks.append({
            "summary": "未发现显著结构性风险",
            "detail": "行业集中度与个股权重均在常规阈值内。",
        })
    return risks


def _compute_risk_metrics(codes: List[str], weights: List[float]) -> Dict:
    """计算行业分布、HHI 与规则化风险项（底层实现，供 risk_alerts 与 full_report 复用）。"""
    industry_dist = _common.build_industry_distribution(codes, weights)
    hhi = sum(w * w for w in industry_dist.values())
    risks = _rule_based_risks(industry_dist, hhi, dict(zip(codes, weights)))

    fmt = _common.get_format_advisor()
    alerts = fmt.format_risk_alerts(risks, disclaimer="规则化风险提示（非 AI 生成），仅供参考，不构成投资建议。")

    return {
        "industry_distribution": industry_dist,
        "industry_hhi": hhi,
        "risk_items": [
            {**r, "source": "rule_based"} for r in risks
        ],
        "alerts": alerts,
    }


def portfolio_risk_alerts(codes: List[str], weights: List[float]) -> str:
    """
    分析组合行业分布并给出规则化风险指标（行业集中度 HHI、个股权重集中度）。

    本工具不含 LLM 调用，只返回结构化指标与规则化风险项（source=rule_based）；
    风险解读文本由上层 AI 基于返回数据生成。

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
        data 包含 industry_distribution / industry_hhi / risk_items / alerts。
        行业信息查询失败时归入"未知行业"并在 risk_items 中提示。
    """
    tool = "portfolio_risk_alerts"
    try:
        codes, weights = _common.validate_portfolio(codes, weights)
        data = _compute_risk_metrics(codes, weights)
        return _common.make_response(tool, data)
    except ValueError as e:
        return _common.error_response(tool, str(e))
    except Exception as e:
        return _common.error_response(tool, f"风险指标计算失败: {e}")
