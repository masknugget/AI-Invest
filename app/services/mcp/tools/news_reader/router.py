"""
News Reader 路由工具（流水线阶段2，独立职责模块）。

单一职责：根据 extract_news_meta 的结构化提取结果，由服务端 LLM 决策应激活哪些
分析师，返回推荐的 agent 名单 + 可直接调用的工具名 + 路由理由/降级方案。

与其他模块正交：
- pipeline.py  提取 / 对齐 / 一体式封装
- analysts.py  分析师执行（本模块路由决策后由平台 LLM 并行调用）
- contract.py  校验与响应封装
本模块只做「选哪个分析师」的决策，不触发任何分析、不生成综合文案。
"""

from __future__ import annotations

from app.services.mcp.tools.news_reader import contract
from app.services.mcp.tools.news_reader.analysts import agent_tool_name
from app.services.news_analysis import service


def route_news_analysts(content: str, meta: str) -> str:
    """
    阶段2 路由决策：根据 extract_news_meta 的结果，由服务端 LLM 推荐应调用哪些分析师工具。

    用法：先调用 extract_news_meta 得到 meta，将其返回 JSON 的 data 字段原样作为
    meta 传入本工具；本工具返回推荐的分析师清单（agent_names + 可直接调用的 tools），
    随后即可对这些分析师工具并行发起调用（并发 ≤3）。
    若你已能依据 data_label 按路由规则自行判断（见 server instructions），可跳过本工具。

    返回 data：{"count": N, "agent_names": ["MacroAgent", ...],
    "tools": ["macro_analyst", ...]（可直接调用的 MCP 工具名）,
    "reasoning": "路由决策说明", "routing_plan": {完整路由计划，含 execution_dag}}。
    本工具只做路由决策、不生成分析；综合解读文案仍由你（平台 LLM）撰写。

    参数
    ----
    content : str
        新闻正文。
    meta : str
        extract_news_meta 返回 JSON 的 data 字段，原样回传；
        误传完整响应封装也能自动兼容。
    """
    tool = "route_news_analysts"
    content = contract.validate_content(content)
    meta_dict = contract.parse_meta(meta)
    print(f"[router] route_news_analysts: 调用 service.route_news, 内容长度={len(content)}")
    routing = service.route_news(content, meta_dict)
    # 过滤幻觉 Agent，仅保留 factory 合法名单，并转为可直接调用的工具名
    valid = set(contract.list_valid_agents())
    agent_names = [a for a in routing.get("agent_names", []) if a in valid]
    tools = [agent_tool_name(a) for a in agent_names]
    print(f"[router] route_news_analysts: 完成, 推荐 agents={agent_names}")
    return contract.make_response(
        tool,
        {
            "count": len(agent_names),
            "agent_names": agent_names,
            "tools": tools,
            "reasoning": routing.get("reasoning", ""),
            "routing_plan": routing.get("routing_plan", {}),
        },
    )
