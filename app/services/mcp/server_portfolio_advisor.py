"""
AI-Invest Portfolio Advisor MCP 服务入口

使用 FastMCP 暴露投资组合分析能力（全部纯计算、零 LLM 调用）：
- portfolio_diagnosis             组合五维评分
- portfolio_risk_alerts           行业分布 + 规则化风险指标
- portfolio_rebalance_suggestion  调仓建议
- portfolio_stress_test           压力测试
- portfolio_full_report           组合全景报告

设计原则：server 只返回结构化指标，风险提示/调仓理由/报告解读等文本
由平台侧 AI 基于工具返回数据生成（平台 AI 已有 LLM 调用能力），
避免 平台AI -> MCP -> 我方LLM 的嵌套往返，降低成本与延迟。

运行方式：
    python -m app.services.mcp.server_portfolio_advisor
    # 或
    python app/services/mcp/server_portfolio_advisor.py

默认 streamable-http 传输，端口 8087。
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from fastmcp import FastMCP

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("app.services.mcp.server_portfolio_advisor")

# ----------------------------------------------------------------------
# FastMCP 实例
# ----------------------------------------------------------------------

mcp = FastMCP(
    name="ai-invest-portfolio-advisor-mcp",
    instructions=(
        "你是 AI-Invest 投资组合分析助手的 MCP 服务。\n"
        "所有工具均为纯计算，返回结构化指标数据，不做任何 LLM 文本生成。\n"
        "可用工具：\n"
        "- portfolio_diagnosis: 组合五维评分（回撤控制/分散度/仓位效率/收益稳定性/风格平衡）\n"
        "- portfolio_risk_alerts: 行业分布、集中度 HHI 与规则化风险项\n"
        "- portfolio_rebalance_suggestion: 基于候选池预计算得分的调仓建议\n"
        "- portfolio_stress_test: 历史/宏观/行业三类压力测试\n"
        "- portfolio_full_report: 五维评分+风险+全场景压力测试的组合全景\n"
        "风险提示、调仓理由与报告解读请由你（调用方 AI）基于工具返回的结构化数据自行生成。\n"
        "股票代码使用 baostock 风格（如 sh.600000、sz.000001、hk.00700）；"
        "weights 允许总和不为 1，服务端自动归一化。"
    ),
)

# ----------------------------------------------------------------------
# 注册 MCP 工具
# ----------------------------------------------------------------------

from app.services.mcp.tools.portfolio_advice import (
    portfolio_diagnosis,
    portfolio_full_report,
    portfolio_rebalance_suggestion,
    portfolio_risk_alerts,
    portfolio_stress_test,
)

mcp.add_tool(portfolio_diagnosis)
mcp.add_tool(portfolio_risk_alerts)
mcp.add_tool(portfolio_rebalance_suggestion)
mcp.add_tool(portfolio_stress_test)
mcp.add_tool(portfolio_full_report)


@mcp.custom_route("/health_mcp", methods=["GET"])
async def health_check(request: Request) -> Response:
    return JSONResponse({"status": "ok"})


if __name__ == "__main__":
    mcp.run(
        host="0.0.0.0",
        port=8087,
        transport="streamable-http",
    )
