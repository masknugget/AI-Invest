"""
News Reader 存储与发现查询工具：检索 insight_agg 中的历史新闻分析、
查询可用分析师清单。

与流水线工具（pipeline.py）职责正交：不触发任何 LLM 调用，只读 MongoDB / factory 元数据。
"""

from __future__ import annotations

from typing import List

from app.services.mcp.tools.news_reader import contract
from app.services.news_analysis import store


async def search_news_insights(
    query: str = "",
    stock_code: str = "",
    limit: int = contract.LIMIT_DEFAULT,
) -> str:
    """
    检索 insight_agg 中的历史新闻分析（按标题/摘要/标签/关键词或股票代码）。

    零 LLM 调用，只读 MongoDB；适用于「最近关于 XX 的新闻分析」「某只股票的
    历史资讯结论」等回溯类问题。

    返回 data：{"count": 条数, "query": 关键词, "stock_code": 代码,
    "items": [历史分析记录]}，按 create_time 倒序。
    """
    tool = "search_news_insights"
    try:
        limit = contract.validate_limit(limit)
        items = await store.search_insights(
            query=query or None,
            stock_code=stock_code or None,
            limit=limit,
        )
        return contract.make_response(
            tool,
            {
                "count": len(items),
                "query": query,
                "stock_code": stock_code,
                "items": items,
            },
        )
    except ValueError as e:
        return contract.error_response(tool, str(e))
    except Exception as e:
        return contract.error_response(tool, f"检索历史分析失败: {e}")


async def list_news_analysts() -> str:
    """
    查询当前可用的全部新闻分析师工具清单。

    不确定该调用哪个分析师、或需要向用户介绍有哪些分析师时，先调用本工具。
    零 LLM 调用，毫秒级返回；清单与分析师工具本身均来自 factory 单一事实来源。

    返回 data：{"count": 分析师数量, "analysts": [{"agent_name", "tool_name", "specialty"}]}。
    其中 tool_name 即可直接调用的 MCP 工具名（如 macro_analyst），
    specialty 为该分析师的中文专长与方法论。
    """
    tool = "list_news_analysts"
    try:
        from recommender.news_reader.agents.analyst.factory import (
            create_analyst,
            list_agent_names,
        )

        from app.services.mcp.tools.news_reader.analysts import agent_tool_name

        analysts: List[dict] = []
        for agent_name in list_agent_names():
            _, specialty = create_analyst(agent_name)
            analysts.append({
                "agent_name": agent_name,
                "tool_name": agent_tool_name(agent_name),
                "specialty": specialty,
            })
        return contract.make_response(
            tool, {"count": len(analysts), "analysts": analysts}
        )
    except Exception as e:
        return contract.error_response(tool, f"查询分析师清单失败: {e}")
