"""
分析师工具工厂：将 factory 中的每个分析 Agent 暴露为独立 MCP 工具。

单一事实来源：工具清单、中文专长（title / description）均来自
recommender.news_reader.agents.analyst.factory（_Mapping / _MappingName，
经公开的 create_analyst / list_agent_names 访问），新增 Agent 时
本文件与 server 注册均无需改动。

平台 LLM 视角：每个分析师是一等工具（macro_analyst / micro_analyst / ...），
调用前需先经 extract_news_meta 获取 meta；多个分析师可并行调用（并发 ≤3）。
"""

from __future__ import annotations

import re
from typing import List

from fastmcp.tools import Tool

from app.services.mcp.tools.news_reader import pipeline

# 分析师工具标签，便于客户端按类别过滤
ANALYST_TOOL_TAGS = {"news-analyst"}

_TOOL_NAME_SUFFIX = "analyst"
_AGENT_SUFFIX = "Agent"

_DESCRIPTION_TEMPLATE = """\
{specialty}专家分析工具（内部 Agent: {agent_name}）。

用法：先调用 extract_news_meta 获取结构化提取结果，将其返回 JSON 的
data 字段原样作为 meta 传入（误传完整响应封装也能自动兼容）。
可对多个分析师工具并行发起调用（建议并发 ≤3，服务端另有信号量限流）。

返回 data：{{"agent_name": "{agent_name}", "report": "Markdown 分析报告"}}。
报告为中间素材，面向用户的综合解读由你（平台 LLM）基于各分析师报告撰写。
"""


def agent_tool_name(agent_name: str) -> str:
    """Agent 名转工具名：MacroAgent -> macro_analyst，TechnicalHLAgent -> technical_hl_analyst。"""
    stem = (
        agent_name[: -len(_AGENT_SUFFIX)]
        if agent_name.endswith(_AGENT_SUFFIX)
        else agent_name
    )
    snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", stem).lower()
    return f"{snake}_{_TOOL_NAME_SUFFIX}"


def _make_caller(agent_name: str, tool_name: str):
    async def _analyst_tool(content: str, meta: str) -> str:
        return await pipeline.analyst_response(
            content, meta, agent_name=agent_name, tool_name=tool_name
        )

    return _analyst_tool


def build_analyst_tools() -> List[Tool]:
    """按 factory 中的 Agent 清单生成全部分析师 MCP 工具。"""
    from recommender.news_reader.agents.analyst.factory import (
        create_analyst,
        list_agent_names,
    )

    tools: List[Tool] = []
    for agent_name in list_agent_names():
        _, specialty = create_analyst(agent_name)
        tool_name = agent_tool_name(agent_name)
        tools.append(
            Tool.from_function(
                _make_caller(agent_name, tool_name),
                name=tool_name,
                title=specialty.split("（")[0].strip(),
                description=_DESCRIPTION_TEMPLATE.format(
                    specialty=specialty,
                    agent_name=agent_name,
                ),
                tags=set(ANALYST_TOOL_TAGS),
            )
        )
    return tools
