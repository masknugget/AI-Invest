"""
新闻分析服务层。

对 recommender.news_reader.consumer.news 异步流水线的封装，供 REST 服务与 MCP 工具使用。

两类入口：
- 阶段级函数（MCP 拆分工具模式，平台 LLM 负责路由与综合文案）：
    extract_meta(content)                       阶段1：NER/标签/事件 三路并行提取（带缓存）
    run_analyst(content, meta, agent_name)      阶段3：单分析 Agent
    finalize(content, meta, analyses, save)     阶段5：结构化对齐 + 可选入库
- 一体式：
    analyze_news(content, save)                 异步并行全流程（带缓存），
                                                供无法多轮编排的客户端使用

缓存键见 cache.py；save=True 时通过 store.py 写入 MongoDB insight_agg。
"""

from __future__ import annotations

from typing import Any, Dict

from recommender.news_reader.consumer.news import (
    aextract_meta,
    afinalize,
    apipeline_news,
    arun_analyst,
)

from app.services.news_analysis import cache, store

DEFAULT_AGENTS = ["MicroAgent", "SentimentAgent"]


def _validate_content(content: str) -> str:
    if not content or not content.strip():
        raise ValueError("新闻内容不能为空")
    return content


async def extract_meta(content: str) -> Dict[str, Any]:
    """阶段1：结构化提取（命名实体 + 分类标签 + 事件关系），三路 LLM 并行。

    命中 Redis 缓存时直接返回（零 LLM 调用）。返回 dict 含
    data_ner / data_label / data_event。
    """
    content = _validate_content(content)

    key = cache.make_key(content, cache.META_SUFFIX)
    cached = await cache.get_json(key)
    if cached is not None:
        return cached

    meta = await aextract_meta(content)
    await cache.set_json(key, meta)
    return meta


async def run_analyst(content: str, meta: Dict[str, Any], agent_name: str) -> str:
    """阶段3：运行单个新闻分析 Agent，返回 Markdown 分析报告。

    agent_name 非法时抛 ValueError（见 recommender.news_reader factory._Mapping）。
    """
    content = _validate_content(content)
    if not agent_name:
        raise ValueError("agent_name 不能为空")
    return await arun_analyst(content, meta, agent_name)


async def finalize(
    content: str,
    meta: Dict[str, Any],
    analyses: Dict[str, str],
    save: bool = True,
) -> Dict[str, Any]:
    """阶段5：将多 Agent 分析结果结构化为标准资讯 JSON（align_data schema）。

    save=True 时写入 MongoDB insight_agg 集合（需先初始化数据库连接）。
    """
    content = _validate_content(content)
    if not analyses:
        raise ValueError("analyses 不能为空（至少包含一个 Agent 的分析结果）")

    data_align = await afinalize(content, meta, analyses)
    if save:
        await store.save_insight(dict(data_align))
    return data_align


async def analyze_news(content: str, save: bool = False) -> Dict[str, Any]:
    """一体式新闻分析：提取 → 服务端路由 → 并发 Agent → 结构化对齐。

    综合报告/解读文案由调用方（平台 LLM）基于返回的各 Agent 结果撰写，
    服务端不再生成 data_report。命中 Redis 缓存时零 LLM 直接返回。

    save=True 时 data_align 写入 MongoDB insight_agg（仅本次新分析会入库，
    缓存命中不会重复入库）。
    """
    content = _validate_content(content)

    key = cache.make_key(content)
    cached = await cache.get_json(key)
    if cached is not None:
        return cached

    # 拆分工具模式下报告由平台 LLM 撰写；一体式为兼容旧行为仍生成综合报告
    out_data = await apipeline_news(content, with_router=True, with_report=True)
    await cache.set_json(key, out_data)

    if save:
        data_align = out_data.get("data_align")
        if data_align:
            await store.save_insight(dict(data_align))
    return out_data
