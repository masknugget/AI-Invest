"""
新闻分析流水线的 LLM 调用汇聚点。

配置注入（不再有硬编码 API key），按优先级读取环境变量：
- NEWS_READER_API_KEY       : LLM API key（最高优先级）
- DASHSCOPE_API_KEY         : 百炼 API key
- OPENAI_API_KEY            : OpenAI 兼容 key
- NEWS_READER_BASE_URL      : 默认 https://dashscope.aliyuncs.com/compatible-mode/v1
- NEWS_READER_MODEL         : 默认模型（提取阶段小模型，默认 qwen3.5-flash）
- NEWS_READER_ANALYST_MODEL : 分析 Agent 使用的大模型（缺省与默认模型一致）

chat_once  : 同步入口（兼容旧调用 pipeline_news / dev.py）
achat_once : 异步入口（apipeline_news / MCP 拆分工具使用）

重试策略：最多 2 次重试（共 3 次尝试），429/超时/服务端错误指数退避；
单次调用超时 30s。
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from functools import lru_cache
from typing import List, Optional

from openai import APIError, APITimeoutError, AsyncOpenAI, OpenAI, RateLimitError
from openai.types.chat import ChatCompletionMessageParam

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen3.5-flash"

_MAX_RETRIES = 2  # 最多重试 2 次（共 3 次尝试）
_TIMEOUT = 30.0  # 单次调用超时 30s
_BACKOFF_BASE = 1.5  # 退避基数（秒）


def get_api_key() -> str:
    """按优先级解析 LLM API key，未配置时抛 RuntimeError。"""
    key = (
        os.environ.get("NEWS_READER_API_KEY")
        or os.environ.get("DASHSCOPE_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    )
    if not key:
        raise RuntimeError(
            "未配置新闻分析 LLM API key，请设置环境变量 NEWS_READER_API_KEY"
            "（或 DASHSCOPE_API_KEY / OPENAI_API_KEY）"
        )
    return key


def get_base_url() -> str:
    return os.environ.get("NEWS_READER_BASE_URL", DEFAULT_BASE_URL)


def get_default_model() -> str:
    """默认模型（提取等轻量阶段使用）。"""
    return os.environ.get("NEWS_READER_MODEL", DEFAULT_MODEL)


def get_analyst_model() -> str:
    """分析 Agent 使用的模型（缺省与默认模型一致）。"""
    return os.environ.get("NEWS_READER_ANALYST_MODEL", get_default_model())


@lru_cache(maxsize=1)
def _sync_client() -> OpenAI:
    return OpenAI(
        api_key=get_api_key(),
        base_url=get_base_url(),
        timeout=_TIMEOUT,
        max_retries=0,  # 重试由本模块统一控制
    )


@lru_cache(maxsize=1)
def _async_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=get_api_key(),
        base_url=get_base_url(),
        timeout=_TIMEOUT,
        max_retries=0,
    )


def _build_messages(
    user_prompt: str, sys_prompt: Optional[str]
) -> List[ChatCompletionMessageParam]:
    messages: List[ChatCompletionMessageParam]
    if sys_prompt is None:
        messages = [{"role": "user", "content": user_prompt}]
    else:
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ]
    return messages


def _should_retry(exc: Exception) -> bool:
    """429 限流 / 超时 / 5xx 服务端错误才重试，4xx 请求错误直接抛。"""
    return isinstance(exc, (RateLimitError, APITimeoutError, APIError))


def chat_once(
    user_prompt: str,
    sys_prompt: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """同步单轮 LLM 调用（兼容旧接口；新增 model 参数支持分阶段选模型）。"""
    messages = _build_messages(user_prompt, sys_prompt)
    model = model or get_default_model()
    client = _sync_client()

    for attempt in range(_MAX_RETRIES + 1):
        try:
            completion = client.chat.completions.create(model=model, messages=messages)
            content = completion.choices[0].message.content
            if content is None:
                raise RuntimeError("LLM 返回内容为空")
            return content
        except Exception as e:
            if attempt < _MAX_RETRIES and _should_retry(e):
                wait = _BACKOFF_BASE * (2 ** attempt)
                logger.warning(
                    "chat_once 调用失败（第 %d 次）: %s，%.1fs 后重试",
                    attempt + 1, e, wait,
                )
                time.sleep(wait)
                continue
            raise
    raise RuntimeError("LLM 调用失败：重试次数耗尽")


async def achat_once(
    user_prompt: str,
    sys_prompt: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """异步单轮 LLM 调用，供并行流水线（asyncio.gather）使用。"""
    messages = _build_messages(user_prompt, sys_prompt)
    model = model or get_default_model()
    client = _async_client()

    for attempt in range(_MAX_RETRIES + 1):
        try:
            completion = await client.chat.completions.create(model=model, messages=messages)
            content = completion.choices[0].message.content
            if content is None:
                raise RuntimeError("LLM 返回内容为空")
            return content
        except Exception as e:
            if attempt < _MAX_RETRIES and _should_retry(e):
                wait = _BACKOFF_BASE * (2 ** attempt)
                logger.warning(
                    "achat_once 调用失败（第 %d 次）: %s，%.1fs 后重试",
                    attempt + 1, e, wait,
                )
                await asyncio.sleep(wait)
                continue
            raise
    raise RuntimeError("LLM 调用失败：重试次数耗尽")
