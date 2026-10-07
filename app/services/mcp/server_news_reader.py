"""
AI-Invest News Reader MCP 服务入口

使用 FastMCP 暴露财经新闻多智能体分析能力（服务端做结构化提取与确定性
流水线，综合报告/解读由平台侧 LLM 基于工具返回结果撰写）：
- extract_news_meta        结构化提取（NER/标签/事件，三路并行，带缓存）
- macro_analyst 等 12 个分析师工具  每个分析 Agent 一等暴露（按 factory 动态生成）
- finalize_news_analysis   结构化对齐 + 可选入库 insight_agg
- search_news_insights     检索历史新闻分析
- analyze_news             一体式封装（供无法多轮编排的客户端）

依赖：
- LLM API key 经环境变量注入：NEWS_READER_API_KEY（或 DASHSCOPE_API_KEY /
  OPENAI_API_KEY），可选 NEWS_READER_BASE_URL / NEWS_READER_MODEL /
  NEWS_READER_ANALYST_MODEL
- MongoDB（finalize/save 与 search 工具）：lifespan 中自动初始化，
  配置走 app/core/config.py（MONGODB_* 环境变量）
- Redis（可选）：缓存 24h；不可用时自动降级为无缓存

运行方式：
    python -m app.services.mcp.server_news_reader
    # 或
    python app/services/mcp/server_news_reader.py

默认 streamable-http 传输，端口 8088。
"""
from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
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
logger = logging.getLogger("app.services.mcp.server_news_reader")


@asynccontextmanager
async def lifespan(server):
    """初始化 MongoDB（save/search 工具依赖）与 Redis（缓存，可选）。

    任一依赖初始化失败仅告警不中断服务：Mongo 不可用时 save/search 工具
    会在调用时报错；Redis 不可用时缓存自动禁用。
    """
    try:
        from app.core.database import close_database, init_database

        await init_database()
        logger.info("✅ MongoDB 初始化完成")
    except Exception as e:
        logger.warning("⚠️ MongoDB 初始化失败（save/search 工具不可用）: %s", e)

    try:
        from app.core.redis_client import close_redis, init_redis

        await init_redis()
        logger.info("✅ Redis 初始化完成")
    except Exception as e:
        logger.warning("⚠️ Redis 初始化失败（新闻缓存禁用）: %s", e)

    yield

    for close in ("close_database", "close_redis"):
        try:
            if close == "close_database":
                from app.core.database import close_database as _close
            else:
                from app.core.redis_client import close_redis as _close
            await _close()
        except Exception as e:
            logger.warning("关闭 %s 失败: %s", close, e)


# ----------------------------------------------------------------------
# FastMCP 实例
# ----------------------------------------------------------------------

mcp = FastMCP(
    name="ai-invest-news-reader-mcp",
    instructions=(
        "你是 AI-Invest 财经新闻分析助手的 MCP 服务。\n"
        "服务端负责结构化提取与分析师执行；新闻解读、综合报告等文案"
        "由你（平台 LLM）基于各分析师工具返回的报告撰写，禁止要求服务端生成综合报告。\n"
        "可用工具：\n"
        "- extract_news_meta: 结构化提取（实体/标签/事件），约 2~6 秒，三路并行，"
        "重复新闻命中缓存零 LLM 调用。\n"
        "- 12 个分析师工具（macro_analyst / industry_analyst / micro_analyst / "
        "event_analyst / valuation_analyst / technical_analyst / technical_hl_analyst / "
        "sentiment_analyst / dividend_analyst / fundamental_analyst / portfolio_analyst / "
        "risk_analyst）：每个对应一位分析专家，调用前先调 extract_news_meta 并将 "
        "返回 JSON 的 data 字段作为 meta 原样传入；可对多个分析师并行发起（并发 ≤3）。\n"
        "- finalize_news_analysis: 结构化对齐并可选入库（save=True 写入 insight_agg），"
        "仅当需要结构化数据/保存时调用。\n"
        "- search_news_insights: 检索历史分析。\n"
        "- list_news_analysts: 查询可用分析师工具清单（名称 + 专长），零 LLM 调用。\n"
        "- analyze_news（一体式）: 完整新闻分析，串行约 15~40 秒，"
        "仅供无法多轮编排的客户端使用。\n"
        "路由规则（extract_news_meta 返回 data_label 后选用对应分析师工具）：\n"
        "  impact_level 含 MACRO            → macro_analyst\n"
        "  impact_level 含 INDUSTRY/CHAIN   → industry_analyst\n"
        "  impact_level 含 COMPANY          → micro_analyst\n"
        "  news_type 含 EARNINGS            → micro_analyst + valuation_analyst\n"
        "  news_type 含 EVENT_REPO          → event_analyst\n"
        "  asset_class=EQUITY 且 urgency≥P1 → sentiment_analyst\n"
        "  news_type 含 RUMOR               → 追加 risk_analyst\n"
        " 默认/不确定                       → micro_analyst + sentiment_analyst\n"
        "不确定有哪些分析师可用时，先调用 list_news_analysts 查询全部分析师及其专长。\n"
        "典型流程：extract_news_meta → (并行调用若干分析师工具) → 你自行综合解读；"
        "仅当需要结构化数据/保存时调用 finalize_news_analysis。"
    ),
    lifespan=lifespan,
)

# ----------------------------------------------------------------------
# 注册 MCP 工具
# ----------------------------------------------------------------------

from app.services.mcp.tools.news_reader import (
    analyze_news,
    build_analyst_tools,
    extract_news_meta,
    finalize_news_analysis,
    list_news_analysts,
    search_news_insights,
)

mcp.add_tool(extract_news_meta)
mcp.add_tool(list_news_analysts)
# 12 个分析师工具按 factory 清单动态生成（单一事实来源）
for _analyst_tool in build_analyst_tools():
    mcp.add_tool(_analyst_tool)
mcp.add_tool(finalize_news_analysis)
mcp.add_tool(search_news_insights)
mcp.add_tool(analyze_news)


@mcp.custom_route("/health_mcp", methods=["GET"])
async def health_check(request: Request) -> Response:
    return JSONResponse({"status": "ok"})


if __name__ == "__main__":
    mcp.run(
        host="0.0.0.0",
        port=8088,
        transport="streamable-http",
    )
