"""
AI-Invest MCP 服务入口

使用 FastMCP 暴露项目内部能力：
- 股票分析（services/analysis）
- 股票信息/语义搜索（services/search）
- 组合调仓建议（services/portfolio_advisor）

运行方式：
    python -m app.services.mcp.server
    # 或
    python app/services/mcp/server.py

默认使用 stdio 传输，也可通过 --transport sse 以 HTTP SSE 方式启动。
"""
from __future__ import annotations
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent.parent
print(project_root)
sys.path.insert(0, str(project_root))

import json
import logging
import sys
from pathlib import Path
from typing import Any

from starlette.responses import JSONResponse, Response
from starlette.requests import Request

# 确保项目根目录在 PYTHONPATH 中
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastmcp import FastMCP

# 日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("app.services.mcp.server")

# ----------------------------------------------------------------------
# FastMCP 实例
# ----------------------------------------------------------------------

mcp = FastMCP(
    name="ai-invest-mcp",
    instructions=(
        "你是 AI-Invest 股票分析助手的 MCP 服务。\n"
        "可用工具：\n"
        "- chat: 与 AI-Invest 投资助手进行对话/问答\n"
        "- analyze_stock: 对单只股票进行多智能体深度分析\n"
        "- get_stock_info: 获取股票基础信息\n"
        "- get_mds_stock_prices: 从 MDS 查询最新股票日行情\n"
        "- get_mds_stock_headlines: 从 MDS 查询股票新闻\n"
        "- get_mds_financial_statements: 从 MDS 查询股票财务报表\n"
        "MDS 工具的 market 参数支持 HK 和 CN；股票代码可带 .HK/.SH/.SZ/.BJ 后缀。"
    ),
)


def greet(name: str) -> str:
    return f"Hello, {name}!"


# ----------------------------------------------------------------------
# 注册 MCP 工具
# ----------------------------------------------------------------------

from app.services.mcp.tools.stock_info import get_stock_info
from app.services.mcp.tools.stock_analysis import analyze_stock
from app.services.mcp.tools.breaking_news import get_breaking_news
from app.services.mcp.tools.mds_stock_data import (
    get_mds_financial_statements,
    get_mds_stock_headlines,
    get_mds_stock_prices,
)

mcp.add_tool(get_stock_info)
mcp.add_tool(analyze_stock)
mcp.add_tool(get_breaking_news)
mcp.add_tool(greet)
mcp.add_tool(get_mds_stock_prices)
mcp.add_tool(get_mds_stock_headlines)
mcp.add_tool(get_mds_financial_statements)


@mcp.custom_route("/health_mcp", methods=["GET"])
async def health_check(request: Request) -> Response:
    return JSONResponse({"status": "ok"})

if __name__ == "__main__":
    mcp.run(
        host='0.0.0.0',
        port=8086,
        transport="streamable-http",
    )
