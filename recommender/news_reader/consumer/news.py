"""
财经新闻多智能体分析流水线。

提供两种入口：
- pipeline_news(content)      同步一体式（兼容 dev.py 等旧调用），串行执行
- apipeline_news(content)     异步一体式，阶段1三路并行 + 阶段3 Agent 并发限流

MCP 拆分工具模式（平台 LLM 负责路由与综合文案）使用阶段级函数：
- aextract_meta(content)                    阶段1：NER / 标签 / 事件 三路并行提取
- arun_analyst(content, meta, agent_name)   阶段3：单分析 Agent
- afinalize(content, meta, analyses)        阶段5：结构化对齐（报告阶段由平台 LLM 承担）
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from recommender.news_reader.agents.analyst.factory import create_analyst
from recommender.news_reader.agents.pipelines.event import prompt_event
from recommender.news_reader.agents.pipelines.labels import prompt_labels
from recommender.news_reader.agents.pipelines.ner import prompt_ner
from recommender.news_reader.agents.pipelines.router import prompt_router
from recommender.news_reader.agents.report import prompt_report
from recommender.news_reader.agents.reporter.align_data import prompt_align_data
from recommender.news_reader.llms import achat_once, chat_once, get_analyst_model
from recommender.news_reader.utils import gen_uuid, parse_json_from_llm

# 阶段3 分析 Agent 最大并发数
MAX_PARALLEL_AGENTS = 4

# 每个事件循环一个信号量（跨 loop 复用 Semaphore 会绑定错误的事件循环）
_loop_semaphores: Dict[int, asyncio.Semaphore] = {}


def _get_agent_semaphore() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    sem = _loop_semaphores.get(id(loop))
    if sem is None:
        sem = asyncio.Semaphore(MAX_PARALLEL_AGENTS)
        _loop_semaphores[id(loop)] = sem
    return sem


def _content_block(content: str) -> str:
    return f"""
    # 新闻内容
    {content}
    """


def _p_data_block(content: str, out_ner: str, out_label: str, out_event: str) -> str:
    """拼装喂给路由 / 分析 Agent 的上下文字符串。"""
    return f"""
    # 新闻内容
    {content}

    # ner
    {out_ner}

    # label
    {out_label}

    # event
    {out_event}

    """


def _normalize_agents(primary_agents: List[Dict[str, Any]]) -> List[str]:
    return [agent for i in primary_agents if (agent := i.get("agent"))]


# ----------------------------------------------------------------------
# 阶段级函数（MCP 拆分工具模式）
# ----------------------------------------------------------------------

async def aextract_meta(content: str) -> Dict[str, Any]:
    """阶段1：对新闻做结构化提取（NER / 分类标签 / 事件关系），三路并行。

    返回 dict：{"data_ner": ..., "data_label": ..., "data_event": ...}
    """
    content_str = _content_block(content)

    p_ner = prompt_ner()
    p_labels = prompt_labels()
    p_event = prompt_event()

    out_ner, out_label, out_event = await asyncio.gather(
        achat_once(p_ner + content_str),
        achat_once(p_labels + content_str),
        achat_once(p_event + content_str),
    )

    return {
        "data_ner": parse_json_from_llm(out_ner),
        "data_label": parse_json_from_llm(out_label),
        "data_event": parse_json_from_llm(out_event),
    }


def build_p_data(content: str, meta: Dict[str, Any]) -> str:
    """根据 meta dict 重建路由 / 分析 Agent 的上下文字符串。"""
    return _p_data_block(
        content,
        json.dumps(meta.get("data_ner", {}), ensure_ascii=False),
        json.dumps(meta.get("data_label", {}), ensure_ascii=False),
        json.dumps(meta.get("data_event", {}), ensure_ascii=False),
    )


async def arun_analyst(content: str, meta: Dict[str, Any], agent_name: str) -> str:
    """阶段3：运行单个分析 Agent，返回 Markdown 分析报告。"""
    p_analyst, _ = create_analyst(agent_name)
    if not p_analyst:
        raise ValueError(
            f"未知分析 Agent: {agent_name}，可选见 factory._Mapping"
        )
    p_data = build_p_data(content, meta)
    return await achat_once(p_data + p_analyst, model=get_analyst_model())


async def arun_analysts(
    content: str,
    meta: Dict[str, Any],
    agent_names: List[str],
) -> Dict[str, str]:
    """阶段3：并发运行多个分析 Agent（信号量限流），返回 {agent_name: 报告}。"""
    sem = _get_agent_semaphore()

    async def _run(name: str) -> tuple:
        async with sem:
            return name, await arun_analyst(content, meta, name)

    results = await asyncio.gather(*[_run(n) for n in agent_names])
    return dict(results)


async def aroute_agents(content: str, meta: Dict[str, Any]) -> List[str]:
    """阶段2（可选）：服务端 LLM 路由，返回建议的 Agent 名列表。

    MCP 拆分工具模式下由平台 LLM 按规则决策，通常不需要调用本函数。
    """
    p_router = prompt_router()
    out_router = await achat_once(build_p_data(content, meta) + p_router)
    data_router = parse_json_from_llm(out_router)
    return _normalize_agents(data_router.get("routing_plan", {}).get("primary_agents", []))


async def afinalize(
    content: str,
    meta: Dict[str, Any],
    analyses: Dict[str, str],
    article_id: Optional[str] = None,
    create_time: Optional[str] = None,
) -> Dict[str, Any]:
    """阶段5：结构化对齐为标准资讯 JSON。

    Args:
        content: 新闻正文
        meta: aextract_meta 的返回 dict
        analyses: {agent_name: Markdown 报告}，平台 LLM 可自行补充综合解读
        article_id / create_time: 缺省时自动生成

    返回 align_data schema dict（含 article_id / create_time）。
    """
    article_id = article_id or gen_uuid()
    create_time = create_time or datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

    out_data: Dict[str, Any] = dict(meta)
    out_data.update(analyses)
    out_data["content"] = ["#" + k + "\n" + v for k, v in analyses.items()]

    p_align = prompt_align_data(json.dumps(out_data, ensure_ascii=False))
    out_align = await achat_once(p_align)
    data_align = parse_json_from_llm(out_align)

    data_align["article_id"] = article_id
    data_align["create_time"] = create_time
    return data_align


# ----------------------------------------------------------------------
# 同步一体式流水线（兼容旧调用）
# ----------------------------------------------------------------------

def pipeline_news(content: str) -> Dict[str, Any]:
    article_id = gen_uuid()
    create_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

    content_str = _content_block(content)

    p_ner = prompt_ner()
    p_labels = prompt_labels()
    p_event = prompt_event()

    out_ner = chat_once(p_ner + content_str)
    out_label = chat_once(p_labels + content_str)
    out_event = chat_once(p_event + content_str)

    p_router = prompt_router()
    p_data = _p_data_block(content, out_ner, out_label, out_event)

    out_router = chat_once(p_data + p_router)
    out_router_json = parse_json_from_llm(out_router)

    primary_agents = _normalize_agents(
        out_router_json.get('routing_plan', {}).get('primary_agents', [])
    )

    out_data: Dict[str, Any] = {}
    data_analyst: Dict[str, str] = {}
    for name in primary_agents:
        p_analyst, p_name = create_analyst(name)
        out_analyst = chat_once(p_data + p_analyst, model=get_analyst_model())
        data_analyst[p_name] = out_analyst
        out_data[name] = out_analyst

    data_ner = parse_json_from_llm(out_ner)
    data_label = parse_json_from_llm(out_label)
    data_event = parse_json_from_llm(out_event)
    data_router = parse_json_from_llm(out_router)

    out_data['data_ner'] = data_ner
    out_data['data_label'] = data_label
    out_data['data_event'] = data_event
    out_data['data_router'] = data_router

    p_report = prompt_report()

    content_blocks = ["#" + k + "\n" + v for k, v in data_analyst.items()]
    # 修复：拼接全部 Agent 输出（原实现只取 content[0]，其余 Agent 结果被丢弃）
    data = content_str + p_report + "\n\n".join(content_blocks)

    report = chat_once(data)

    out_data['data_report'] = report
    out_data['content'] = content_blocks

    p_align = prompt_align_data(json.dumps(out_data, ensure_ascii=False))
    out_align = chat_once(p_align)
    data_align = parse_json_from_llm(out_align)

    data_align['article_id'] = article_id
    data_align['create_time'] = create_time

    out_data['article_id'] = article_id
    out_data['data_align'] = data_align
    return out_data


# ----------------------------------------------------------------------
# 异步一体式流水线（一体式 MCP 工具 / 服务层使用）
# ----------------------------------------------------------------------

async def apipeline_news(
    content: str,
    agent_names: Optional[List[str]] = None,
    with_router: bool = True,
    with_report: bool = True,
) -> Dict[str, Any]:
    """异步并行版一体式流水线。

    Args:
        content: 新闻正文
        agent_names: 显式指定分析 Agent 列表（拆分工具模式由平台 LLM 决策后回传）；
                     为 None 时按 with_router 决定服务端路由或走默认 Agent
        with_router: agent_names 为 None 时，是否执行服务端 LLM 路由
        with_report: 是否执行阶段4综合报告（拆分工具模式应关闭，由平台 LLM 撰写）

    返回与 pipeline_news 相同结构的 dict（with_report=False 时无 data_report）。
    """
    article_id = gen_uuid()
    create_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

    # 阶段1：三路提取并行
    meta = await aextract_meta(content)

    # 阶段2：路由决策（可选）
    if agent_names is None:
        if with_router:
            agent_names = await aroute_agents(content, meta)
        if not agent_names:
            agent_names = ["MicroAgent", "SentimentAgent"]

    # 阶段3：多 Agent 并发（信号量限流），分析 Agent 使用大模型
    analyses = await arun_analysts(content, meta, agent_names)

    out_data: Dict[str, Any] = dict(meta)
    out_data.update(analyses)
    out_data['data_analyst_agents'] = agent_names
    content_blocks = ["#" + k + "\n" + v for k, v in analyses.items()]
    out_data['content'] = content_blocks

    # 阶段4：综合报告（可选；拆分工具模式下由平台 LLM 承担）
    if with_report:
        p_report = prompt_report()
        data = _content_block(content) + p_report + "\n\n".join(content_blocks)
        out_data['data_report'] = await achat_once(data)

    # 阶段5：结构化对齐
    data_align = await afinalize(
        content, meta, analyses,
        article_id=article_id, create_time=create_time,
    )

    out_data['article_id'] = article_id
    out_data['data_align'] = data_align
    return out_data
