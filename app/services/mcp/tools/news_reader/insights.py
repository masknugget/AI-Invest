"""
News Reader 存储与发现查询工具：检索 insight_agg 中的历史新闻分析、
查询可用分析师清单。

与流水线工具（pipeline.py）职责正交：不触发任何 LLM 调用，只读 MongoDB / factory 元数据。
"""

from __future__ import annotations

from typing import List

from app.services.mcp.tools.news_reader import contract
from app.services.news_analysis import store


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


async def search_news_insights(
    query: str = "",
    stock_code: str = "",
    limit: int = contract.LIMIT_DEFAULT,
) -> str:
    """
    检索历史新闻分析结果（MongoDB insight_agg 集合）。

    按 title / summary / tags / keywords 关键词匹配和/或股票代码过滤，
    按 create_time 倒序返回。纯查询，无 LLM 调用，毫秒级返回。

    参数
    ----
    query : str
        关键词（正则匹配 title/summary/tags/keywords），默认空（不过滤）。
    stock_code : str
        股票代码（匹配 data_align.stock_codes.code），默认空（不过滤）。
    limit : int
        返回条数上限 1~100，默认 10。

    返回 data：{"count": 命中条数, "items": [分析结果, ...]}，
    每条含 data_align（title/summary/stock_codes/tags/...）与 article_id/create_time。
    解读 item 内容时请结合当前对话上下文，不要照搬原文回复用户。
    """
    tool = "search_news_insights"
    try:
        limit = contract.validate_limit(limit)
        results = await store.search_insights(
            query=query or None,
            stock_code=stock_code or None,
            limit=limit,
        )
        return contract.make_response(
            tool, {"count": len(results), "items": results}
        )
    except ValueError as e:
        return contract.error_response(tool, str(e))
    except Exception as e:
        return contract.error_response(tool, f"检索历史分析失败: {e}")
