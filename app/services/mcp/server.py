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

import argparse
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

from mcp.server.fastmcp import FastMCP

# 日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("app.services.mcp.server")

# ---------------------------------------------------------------------------
# FastMCP 实例
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="ai-invest-mcp",
    instructions=(
        "你是 AI-Invest 股票分析助手的 MCP 服务。\n"
        "可用工具：\n"
        "- chat: 与 AI-Invest 投资助手进行对话/问答\n"
        "- analyze_stock: 对单只股票进行多智能体深度分析\n"
        "- search_stocks: 根据自然语言查询语义搜索股票/文档\n"
        "- get_stock_info: 获取股票基础信息\n"
        "- get_portfolio_advice: 获取组合调仓建议\n"
        "调用时请注意股票代码为 6 位数字（A股）或带后缀代码（港股/美股）。"
    ),
)

def greet(name: str) -> str:
    return f"Hello, {name}!"

# ---------------------------------------------------------------------------
# 注册 MCP 工具
# ---------------------------------------------------------------------------

from app.services.mcp.tools.stock_info import get_stock_info
from app.services.mcp.tools.stock_analysis import analyze_stock
from app.services.mcp.tools.chat import chat

mcp.add_tool(get_stock_info)
mcp.add_tool(analyze_stock)
mcp.add_tool(chat)
mcp.add_tool(greet)


@mcp.custom_route("/health_mcp", methods=["GET"])
async def health_check(request: Request) -> Response:
    return JSONResponse({"status": "ok"})

# ---------------------------------------------------------------------------
# 启动入口
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="AI-Invest MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="MCP 传输协议，默认 stdio",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="SSE 模式监听地址",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="SSE 模式监听端口",
    )
    args = parser.parse_args()

    logger.info("启动 AI-Invest MCP Server, transport=%s", args.transport)

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    elif args.transport in ("sse", "streamable-http"):
        # FastMCP 的 run() 不直接暴露 host/port，
        # 如需自定义 SSE 地址，请改用 mcp.settings 或 ASGI 挂载。
        mcp.run(transport=args.transport)
    else:
        parser.error(f"不支持的传输协议: {args.transport}")


if __name__ == "__main__":
    main()
