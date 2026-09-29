"""
新闻分析服务

对 recommender.news_reader.consumer.news.pipeline_news 的封装：
- pipeline_news 是同步函数，内部包含 6~10 次串行 LLM 调用，单次耗时约 30~120 秒
- 在 async 上下文（如 MCP server）中通过 asyncio.to_thread 调用，避免阻塞事件循环
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict

from recommender.news_reader.consumer.news import pipeline_news


async def analyze_news(content: str) -> Dict[str, Any]:
    """对单条财经新闻进行多智能体深度分析。

    流程：NER / 分类标签 / 事件结构化 → 路由决策 → 多分析 Agent →
    综合报告 → 结构化对齐，返回标准化 JSON。

    Args:
        content: 新闻正文（中文）。

    Returns:
        pipeline_news 的完整输出 dict，含 data_ner / data_label / data_event /
        data_router / data_report / data_align / article_id / create_time 等字段。

    Raises:
        ValueError: content 为空。
        Exception: 流水线任一步骤失败时向上传播（LLM 调用、JSON 解析等）。
    """
    if not content or not content.strip():
        raise ValueError("新闻内容不能为空")

    # pipeline_news 为同步阻塞调用（含多次 LLM 请求），放到线程池执行
    return await asyncio.to_thread(pipeline_news, content)
