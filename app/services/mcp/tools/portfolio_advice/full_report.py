"""
工具：portfolio_full_report —— 组合全景报告（纯计算，零 LLM 调用）。

= 五维评分 + 规则化风险指标 + 全场景压力测试 的结构化汇总。
不默认包含调仓建议（依赖预计算分数文件且计算较重），由调用方按需调 portfolio_rebalance_suggestion。
"""
from __future__ import annotations

from typing import List

from app.services.mcp.tools.portfolio_advice import _common
from app.services.mcp.tools.portfolio_advice.risk_alerts import _compute_risk_metrics


def _compose_comment(scores: dict, composite: float) -> str:
    """基于维度得分生成模板化综合评语（非 AI 生成，供上层 AI 改写/润色）。"""
    ordered = sorted(scores.items(), key=lambda kv: kv[1])
    weakest, weakest_score = ordered[0]
    strongest, strongest_score = ordered[-1]
    dim_cn = {
        "drawdown_control": "抗回撤能力",
        "portfolio_diversification": "资产分散度",
        "position_efficiency": "持仓性价比",
        "return_stability": "收益稳定性",
        "style_balance": "风格均衡",
    }
    return (
        f"组合综合健康分 {composite:.1f}/100。"
        f"优势维度为{dim_cn.get(strongest, strongest)}（{strongest_score:.1f} 分），"
        f"短板维度为{dim_cn.get(weakest, weakest)}（{weakest_score:.1f} 分），"
        "建议结合压力测试与风险指标结果评估组合稳健性。"
    )


def portfolio_full_report(codes: List[str], weights: List[float]) -> str:
    """
    一键获取组合全景：五维评分 + 行业分布与规则化风险指标 + 全场景压力测试。

    供上层 AI 单次调用获得组合全貌，减少多轮工具往返。
    本工具不含 LLM 调用，所有结论性文本由上层 AI 基于返回的结构化数据生成。

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
        data 含 dimensions（五维指标与得分）、risk（行业分布/HHI/规则化风险项）、
        stress（history/scenario/sector 三类全场景损失结果）、report（健康分/评级/模板评语）。
        个别压力场景失败不影响整体，失败信息写入 warnings（status=partial）。
    """
    tool = "portfolio_full_report"
    try:
        codes, weights = _common.validate_portfolio(codes, weights)
        warnings: List[str] = []

        dimension_run = _common.get_dimension_run()
        fmt = _common.get_format_advisor()

        # 1. 五维评分（行情只拉取一次，供评分与历史压力测试复用）
        dfs_map = _common.fetch_quotes(codes)
        dfs = [dfs_map[c] for c in codes]
        dimensions = dimension_run.compute_portfolio_dimensions(dfs, weights)

        # 2. 风险指标
        risk = _compute_risk_metrics(codes, weights)
        if any(ind == "未知行业" for ind in risk["industry_distribution"]):
            warnings.append("部分标的行业信息缺失，风险指标可能不完整")

        # 3. 全场景压力测试
        from recommender.portfolio_advisor.stress_portfolio.history_stress import (
            compute_historical_stress,
        )
        from recommender.portfolio_advisor.stress_portfolio.scenario_stress import (
            compute_scenario_stress,
            list_scenario_names,
        )
        from recommender.portfolio_advisor.stress_portfolio.sector_stress import (
            compute_sector_stress,
            list_sector_names,
        )

        portfolio = _common.build_portfolio_arg(codes, weights)
        stress_warnings: List[str] = []

        history_results = compute_historical_stress(portfolio, dfs_map)

        scenario_results = []
        for name in list_scenario_names():
            try:
                scenario_results.append(
                    compute_scenario_stress(portfolio, name, industry_lookup=_common.industry_lookup)
                )
            except ValueError as e:
                stress_warnings.append(f"宏观情景「{name}」计算跳过: {e}")

        sector_results = []
        for sector in list_sector_names():
            try:
                sector_results.append(
                    compute_sector_stress(portfolio, sector=sector, industry_lookup=_common.industry_lookup)
                )
            except ValueError as e:
                stress_warnings.append(f"行业情景「{sector}」计算跳过: {e}")

        warnings.extend(stress_warnings)

        # 4. 汇总报告（模板评语，非 AI 生成）
        score_dict = dimensions.to_score_dict()
        report = fmt.format_report(
            dimensions,
            comprehensive_str=_compose_comment(score_dict, dimensions.composite_score),
            disclaimer="本报告由规则计算生成（非 AI 生成），仅供参考，不构成投资建议。市场有风险，投资需谨慎。",
        )

        data = {
            "codes": codes,
            "weights": weights,
            "dimensions": {
                "scores": dict(score_dict),
                "drawdown_control": {"max_drawdown": dimensions.drawdown_control.mdd,
                                     "score": dimensions.drawdown_control.score},
                "portfolio_diversification": {
                    "enb_weight_based": dimensions.portfolio_diversification.enb_weight_based,
                    "enb_risk_based": dimensions.portfolio_diversification.enb_risk_based,
                    "score": dimensions.portfolio_diversification.score,
                },
                "position_efficiency": {"sharpe_ratio": dimensions.position_efficiency.sharpe_ratio,
                                        "score": dimensions.position_efficiency.score},
                "return_stability": {"annualized_volatility": dimensions.return_stability.annualized_volatility,
                                     "score": dimensions.return_stability.score},
                "style_balance": {"style_hhi": dimensions.style_balance.style_hhi,
                                  "effective_style_num": dimensions.style_balance.effective_style_num,
                                  "score": dimensions.style_balance.score},
                "composite_score": dimensions.composite_score,
                "geometric_composite_score": dimensions.geometric_composite_score,
                "dimension_weights": dict(dimensions.dimension_weights),
            },
            "risk": risk,
            "stress": {
                "history": history_results,
                "scenario": scenario_results,
                "sector": sector_results,
            },
            "report": report,
        }
        status = "partial" if stress_warnings else "success"
        return _common.make_response(tool, data, status=status, warnings=warnings)
    except ValueError as e:
        return _common.error_response(tool, str(e))
    except Exception as e:
        return _common.error_response(tool, f"全景报告计算失败: {e}")
