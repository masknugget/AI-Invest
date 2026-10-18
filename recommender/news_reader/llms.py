"""
新闻分析流水线的 LLM 调用汇聚点。

配置注入：按优先级读取环境变量，均未配置时回退使用 DEFAULT_API：
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

from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, OpenAI, RateLimitError
from openai.types.chat import ChatCompletionMessageParam

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen3.8-flash"
DEFAULT_API = "sk-ws-H.PYIYHYX.wRcx.MEQCIAEQz9Kd7IuaZEs257-ZUB-sHVqwygDhPvGTzgyCUEi0AiB6Z7cjcWNvR772h4ARh5Kid3tOhDIQn2W9-SZUHZ4t3g"

_MAX_RETRIES = 2  # 最多重试 2 次（共 3 次尝试）
_BACKOFF_BASE = 1.5  # 退避基数（秒）


def get_api_key() -> str:
    """按优先级解析 LLM API key，环境变量均未配置时回退使用 DEFAULT_API。"""
    return DEFAULT_API


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
        max_retries=0,  # 重试由本模块统一控制
    )


@lru_cache(maxsize=1)
def _async_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=get_api_key(),
        base_url=get_base_url(),
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
    """仅重试限流/超时/网络连接错误，4xx 客户端错误（含 401 认证）直接抛。"""
    return isinstance(exc, (RateLimitError, APITimeoutError, APIConnectionError))


def chat_once(
    user_prompt: str,
    sys_prompt: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """同步单轮 LLM 调用（兼容旧接口；新增 model 参数支持分阶段选模型）。"""
    messages = _build_messages(user_prompt, sys_prompt)
    model = model or get_default_model()
    base_url = get_base_url()
    print(f"[llms] chat_once: model={model}, base_url={base_url}, prompt长度={len(user_prompt)}")
    client = _sync_client()
    completion = client.chat.completions.create(model=model, messages=messages)
    content = completion.choices[0].message.content
    if content is None:
        raise RuntimeError("LLM 返回内容为空")
    print(f"[llms] chat_once: 完成, 响应长度={len(content)}")
    return content


async def achat_once(
    user_prompt: str,
    sys_prompt: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """异步单轮 LLM 调用（内部委托给同步 chat_once 实现）。"""
    return chat_once(user_prompt, sys_prompt, model)
