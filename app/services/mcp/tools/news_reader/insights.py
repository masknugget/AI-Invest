"""
News Reader 存储与发现查询工具：检索 insight_agg 中的历史新闻分析、
查询可用分析师清单。

与流水线工具（pipeline.py）职责正交：不触发任何 LLM 调用，只读 MongoDB / factory 元数据。
"""

from __future__ import annotations

from typing import List

from app.services.mcp.tools.news_reader import contract



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
