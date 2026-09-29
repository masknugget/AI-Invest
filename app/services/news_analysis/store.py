"""
新闻分析结果存储层

封装 MongoDB insight_agg 集合的读写，供服务层与 MCP 工具使用。
使用 Motor async 驱动，需在 FastAPI lifespan 初始化数据库后调用。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.database import get_mongo_db

COLLECTION_NAME = "insight_agg"


def get_collection():
    return get_mongo_db()[COLLECTION_NAME]


async def save_insight(data: Dict[str, Any]) -> str:
    """保存一条新闻分析结果，返回 article_id。"""
    article_id = data.get("article_id")
    if not article_id:
        raise ValueError("分析结果缺少 article_id 字段")
    await get_collection().insert_one(data)
    return article_id


async def get_insight(article_id: str) -> Optional[Dict[str, Any]]:
    """按 article_id 查询单条分析结果。"""
    return await get_collection().find_one({"article_id": article_id}, {"_id": 0})


async def search_insights(
    query: Optional[str] = None,
    stock_code: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """检索历史新闻分析结果。

    Args:
        query: 关键词，匹配 title / summary / tags / keywords。
        stock_code: 按股票代码过滤（匹配 stock_codes.code）。
        limit: 返回条数上限，默认 10。

    Returns:
        分析结果列表，按 create_time 倒序。
    """
    filter_doc: Dict[str, Any] = {}
    if query:
        filter_doc["$or"] = [
            {"data_align.title": {"$regex": query, "$options": "i"}},
            {"data_align.summary": {"$regex": query, "$options": "i"}},
            {"data_align.tags": {"$regex": query, "$options": "i"}},
            {"data_align.keywords": {"$regex": query, "$options": "i"}},
        ]
    if stock_code:
        filter_doc["data_align.stock_codes.code"] = stock_code

    cursor = (
        get_collection()
        .find(filter_doc, {"_id": 0})
        .sort("create_time", -1)
        .limit(limit)
    )
    return await cursor.to_list(length=limit)
