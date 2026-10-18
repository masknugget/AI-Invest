"""
新闻分析 Redis 缓存层。

缓存键设计（docs/news_reader_mcp_design.md 6.3）：
- 完整流水线结果："news_reader:" + md5(content)
- 提取阶段子键："news_reader:" + md5(content) + ":meta"
  （换 Agent 组合复跑时可直接命中前置提取结果）
TTL 24h。

Redis 未初始化或不可用时静默降级为不缓存，不打断主流程
（独立运行的 MCP server 在未启动 Redis 时仍可用，只是无缓存）。
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

KEY_PREFIX = "news_reader:"
META_SUFFIX = ":meta"
TTL_SECONDS = 24 * 3600


def _get_client():
    """获取异步 Redis 客户端；未初始化时返回 None（缓存禁用）。"""
    try:
        from app.core.redis_client import get_redis

        return get_redis()
    except Exception as e:
        logger.debug("Redis 不可用，新闻分析缓存禁用: %s", e)
        return None


def make_key(content: str, suffix: str = "") -> str:
    digest = hashlib.md5(content.encode("utf-8")).hexdigest()
    return f"{KEY_PREFIX}{digest}{suffix}"


async def get_json(key: str) -> Optional[Any]:
    client = _get_client()
    if client is None:
        return None
    try:
        value = await client.get(key)
        if value:
            return json.loads(value)
    except Exception as e:
        logger.warning("新闻缓存读取失败 %s: %s", key, e)
    return None


async def set_json(key: str, value: Any, ttl: int = TTL_SECONDS) -> None:
    client = _get_client()
    if client is None:
        return
    try:
        await client.setex(key, ttl, json.dumps(value, ensure_ascii=False))
    except Exception as e:
        logger.warning("新闻缓存写入失败 %s: %s", key, e)


def get_json_sync(key: str) -> Optional[Any]:
    """同步版 get_json（当前实现跳过缓存，直接返回 None）。"""
    # TODO: 实现同步 Redis 缓存读取
    return None


def set_json_sync(key: str, value: Any, ttl: int = TTL_SECONDS) -> None:
    """同步版 set_json（当前实现跳过缓存）。"""
    # TODO: 实现同步 Redis 缓存写入
    pass
