"""
财经新闻多智能体分析流水线。

提供两种入口：
- pipeline_news(content)      同步一体式（兼容 dev.py 等旧调用），串行执行

MCP 拆分工具模式（平台 LLM 负责路由与综合文案）使用阶段级函数：
- extract_meta(content)                    阶段1：NER / 标签 / 事件 三路并行提取
- route_meta(content, meta)                阶段2：LLM 路由决策（返回推荐的分析 Agent）
- run_analyst(content, meta, agent_name)   阶段3：单分析 Agent
- finalize(content, meta, analyses)        阶段5：结构化对齐（报告阶段由平台 LLM 承担）
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Dict, List, Optional

from recommender.news_reader.agents.analyst.factory import create_analyst
from recommender.news_reader.agents.pipelines.event import prompt_event
from recommender.news_reader.agents.pipelines.labels import prompt_labels
from recommender.news_reader.agents.pipelines.ner import prompt_ner
from recommender.news_reader.agents.pipelines.router import prompt_router
from recommender.news_reader.agents.report import prompt_report
from recommender.news_reader.agents.reporter.align_data import prompt_align_data
from recommender.news_reader.llms import chat_once, get_analyst_model
from recommender.news_reader.utils import gen_uuid, parse_json_from_llm

# 阶段3 分析 Agent 最大并发数（保留用于兼容，同步模式下不实际使用）
MAX_PARALLEL_AGENTS = 4


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

def extract_meta(content: str) -> Dict[str, Any]:
    """阶段1：对新闻做结构化提取（NER / 分类标签 / 事件关系），三路并行执行。

    返回 dict：{"data_ner": ..., "data_label": ..., "data_event": ...}
    """
    content_str = _content_block(content)

    p_ner = prompt_ner()
    p_labels = prompt_labels()
    p_event = prompt_event()

    print("[news] extract_meta: 阶段1 - NER / 分类标签 / 事件关系 三路并行提取")
    with ThreadPoolExecutor(max_workers=3) as pool:
        f_ner = pool.submit(chat_once, p_ner + content_str)
        f_label = pool.submit(chat_once, p_labels + content_str)
        f_event = pool.submit(chat_once, p_event + content_str)
        out_ner = f_ner.result()
        out_label = f_label.result()
        out_event = f_event.result()

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


def run_analyst(content: str, meta: Dict[str, Any], agent_name: str) -> str:
    """阶段3：运行单个分析 Agent，返回 Markdown 分析报告。"""
    p_analyst, _ = create_analyst(agent_name)
    if not p_analyst:
        raise ValueError(
            f"未知分析 Agent: {agent_name}，可选见 factory._Mapping"
        )
    p_data = build_p_data(content, meta)
    model = get_analyst_model()
    print(f"[news] run_analyst: 阶段3 - Agent={agent_name}, model={model}")
    return chat_once(p_data + p_analyst, model=model)


def run_analysts(
    content: str,
    meta: Dict[str, Any],
    agent_names: List[str],
) -> Dict[str, str]:
    """阶段3：顺序运行多个分析 Agent，返回 {agent_name: 报告}。"""
    results = {}
    for name in agent_names:
        results[name] = run_analyst(content, meta, name)
    return results


def normalize_routing(data_router: Dict[str, Any]) -> List[str]:
    """从路由结果 dict 提取 primary agent 名列表（纯函数，无 LLM 调用）。"""
    return _normalize_agents(
        data_router.get("routing_plan", {}).get("primary_agents", [])
    )


def route_meta(content: str, meta: Dict[str, Any]) -> Dict[str, Any]:
    """阶段2：服务端 LLM 路由决策，返回完整路由结果 dict。

    含 routing_plan（primary/secondary/tertiary agents、execution_dag）、
    routing_reasoning、fallback_plan。单次 LLM 调用。
    """
    print("[news] route_meta: 阶段2 - 路由决策")
    out_router = chat_once(build_p_data(content, meta) + prompt_router())
    return parse_json_from_llm(out_router)


def route_agents(content: str, meta: Dict[str, Any]) -> List[str]:
    """阶段2（可选）：服务端 LLM 路由，返回建议的 Agent 名列表。

    MCP 拆分工具模式下由平台 LLM 按规则决策，通常不需要调用本函数。
    """
    return normalize_routing(route_meta(content, meta))


def finalize(
    content: str,
    meta: Dict[str, Any],
    analyses: Dict[str, str],
    article_id: Optional[str] = None,
    create_time: Optional[str] = None,
) -> Dict[str, Any]:
    """阶段5：结构化对齐为标准资讯 JSON。

    Args:
        content: 新闻正文
        meta: extract_meta 的返回 dict
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
    print("[news] finalize: 阶段5 - 结构化对齐")
    out_align = chat_once(p_align)
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

    print("[news] pipeline_news: 阶段1 - NER / 分类标签 / 事件关系 三路并行提取")
    with ThreadPoolExecutor(max_workers=3) as pool:
        f_ner = pool.submit(chat_once, p_ner + content_str)
        f_label = pool.submit(chat_once, p_labels + content_str)
        f_event = pool.submit(chat_once, p_event + content_str)
        out_ner = f_ner.result()
        out_label = f_label.result()
        out_event = f_event.result()

    p_data = _p_data_block(content, out_ner, out_label, out_event)

    out_router = chat_once(p_data + prompt_router())
    data_router = parse_json_from_llm(out_router)
    primary_agents = normalize_routing(data_router)

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
# 同步一体式流水线（一体式 MCP 工具 / 服务层使用）
# ----------------------------------------------------------------------

def pipeline_news_sync(
    content: str,
    agent_names: Optional[List[str]] = None,
    with_router: bool = True,
    with_report: bool = True,
) -> Dict[str, Any]:
    """同步一体式流水线。

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

    # 阶段1：顺序提取
    meta = extract_meta(content)

    # 阶段2：路由决策（可选）
    if agent_names is None:
        if with_router:
            agent_names = route_agents(content, meta)
        if not agent_names:
            agent_names = ["MicroAgent", "SentimentAgent"]

    # 阶段3：顺序运行多 Agent
    analyses = run_analysts(content, meta, agent_names)

    out_data: Dict[str, Any] = dict(meta)
    out_data.update(analyses)
    out_data['data_analyst_agents'] = agent_names
    content_blocks = ["#" + k + "\n" + v for k, v in analyses.items()]
    out_data['content'] = content_blocks

    # 阶段4：综合报告（可选；拆分工具模式下由平台 LLM 承担）
    if with_report:
        p_report = prompt_report()
        data = _content_block(content) + p_report + "\n\n".join(content_blocks)
        out_data['data_report'] = chat_once(data)

    # 阶段5：结构化对齐
    data_align = finalize(
        content, meta, analyses,
        article_id=article_id, create_time=create_time,
    )

    out_data['article_id'] = article_id
    out_data['data_align'] = data_align
    return out_data
