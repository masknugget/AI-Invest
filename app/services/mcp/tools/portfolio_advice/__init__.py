"""
Portfolio Advisor MCP 工具包。

直接封装 recommender/portfolio_advisor/ 计算引擎（零引擎改动），
所有工具均为纯计算、零 LLM 调用，只返回结构化指标；
风险提示、调仓理由等文本生成由平台侧 AI 完成。

工具清单：
- portfolio_diagnosis             五维评分
- portfolio_risk_alerts           行业分布 + 规则化风险指标
- portfolio_rebalance_suggestion  调仓建议
- portfolio_stress_test           压力测试
- portfolio_full_report           组合全景报告
"""
from app.services.mcp.tools.portfolio_advice.diagnosis import portfolio_diagnosis
from app.services.mcp.tools.portfolio_advice.risk_alerts import portfolio_risk_alerts
from app.services.mcp.tools.portfolio_advice.rebalance import portfolio_rebalance_suggestion
from app.services.mcp.tools.portfolio_advice.stress_test import portfolio_stress_test
from app.services.mcp.tools.portfolio_advice.full_report import portfolio_full_report

__all__ = [
    "portfolio_diagnosis",
    "portfolio_risk_alerts",
    "portfolio_rebalance_suggestion",
    "portfolio_stress_test",
    "portfolio_full_report",
]
