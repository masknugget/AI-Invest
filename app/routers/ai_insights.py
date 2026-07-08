"""
AI Insights 路由 - 市场洞察卡片 Feed 流

提供 AI 生成的市场洞察卡片流、详情页、风险披露等功能。
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.db.cache import CacheEmbedding
from app.core.db.document import (
    get_insight_by_id,
    get_recommendation_history_docs,
    get_rec_history,
    get_user_profile,
    get_views_insight,
    log_rec_content_history,
    log_rec_history,
    log_views_insight,
)
from app.routers.auth_db import get_current_user
from recommender.user_profile.gen_user_profiles import USER_PROFILE_TAGS
from tradingagents.searcher import VectorStore

logger = logging.getLogger("Insights")
router = APIRouter(tags=["AI Insights"])

# ============================================================
# 常量与枚举
# ============================================================

INSIGHT_TYPES = [
    "MACRO", "PORTFOLIO", "SECTOR", "DIVIDEND",
    "FIFTY_TWO_WEEK", "VOLATILITY", "POPULAR",
]

TYPE_LABELS = {
    "MACRO": ("Macro & Micro", "宏觀與微觀經濟"),
    "PORTFOLIO": ("For You", "為您推薦"),
    "SECTOR": ("Sectors", "板塊"),
    "DIVIDEND": ("High Dividend", "高股息"),
    "FIFTY_TWO_WEEK": ("52-Week High/Low", "52週高低位"),
    "VOLATILITY": ("Big Movers", "大幅波動"),
    "POPULAR": ("Popular", "熱門話題"),
}


def fill_nan(data_dt: Dict[str, Any]) -> Dict[str, Any]:
    """将字典中全为 NaN 的字段替换为空字符串，避免 JSON 序列化异常。"""
    out_data = {}
    for k, v in data_dt.items():
        if isinstance(v, list):
            is_nan = pd.isna(v).all()
        else:
            is_nan = pd.isna(v)
        out_data[k] = "" if is_nan else v
    return out_data


def get_tag_name(name_str: str) -> str:
    """根据内部 tag 名称获取用户画像标签的中文名称。"""
    return USER_PROFILE_TAGS.get(name_str, name_str)


# ============================================================
# 路由
# ============================================================

@router.get("/feed", summary="获取 AI Insights Feed 流")
async def get_feed(
    k: int = Query(3, ge=1, le=30, description="返回数据的天数（控制召回数量）"),
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    获取 AI 洞察卡片 Feed 流，用于首页 "HSBC AI: Market Insights for You" 模块。

    - `k`: 返回数据的天数（控制召回数量），默认 3，最大 30。
    """
    # 兼容旧版：若未取到用户名则使用默认账号
    user_id = user.get("username", "admin123")
    logger.info("begin feed api: user_id=%s k=%d", user_id, k)

    profile = get_user_profile(user_id)
    if not profile:
        logger.warning("feed: user profile not found: user_id=%s", user_id)
        return {"data": [], "count": 0}

    tags = profile.get("generatedTags", [])
    tags_names = [i.get("tag") for i in tags]
    tags_zn = [get_tag_name(i) for i in tags_names]

    # 推荐历史，用于过滤已推荐内容
    history = get_rec_history(user_id)
    logger.info("feed: user_id=%s history_size=%d", user_id, len(history))

    # 向量召回
    vector_store = VectorStore("insight_agg")
    tags_zn_str = " ".join(tags_zn)

    if tags_zn_str in CacheEmbedding:
        vector = CacheEmbedding[tags_zn_str]
    else:
        vector = vector_store.search(tags_zn_str, top_k=50)
        CacheEmbedding[tags_zn_str] = vector

    logger.info("feed: user_id=%s vector_search_size=%d", user_id, len(vector))

    # 过滤已推荐内容
    filtered = {item.id: item for item in vector if item.metadata.get("article_id") not in history}
    result = list(filtered.values())

    # 按评分排序并截取前 k 条
    result_sorted = sorted(result, key=lambda x: x.score, reverse=True)[:k]

    # 记录推荐历史
    rec_ids = [i.metadata.get("article_id") for i in result_sorted]
    data_rec_log = {
        "user_id": user_id,
        "rec_content_ids": rec_ids,
        "create_datetime": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    log_rec_history(data_rec_log)

    out_data = [
        {
            "title": item.metadata.get("title"),
            "uuid": item.metadata.get("article_id"),
            "language": item.metadata.get("language"),
        }
        for item in result_sorted
    ]

    # 保存推荐内容的完整数据
    log_rec_content_history(user_id, out_data)

    logger.info("feed: user_id=%s return_count=%d", user_id, len(out_data))
    return {"data": out_data, "count": len(out_data)}


@router.get("/views/history", summary="获取 Insight 浏览历史")
async def get_insight_views_history(
    pageSize: int = Query(20, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: Dict[str, Any] = Depends(get_current_user),
):
    """获取用户的 Insight 浏览历史记录。"""
    user_id = user.get("username", "unknown")
    logger.info("get_insight_views_history: user_id=%s page=%d pageSize=%d", user_id, page, pageSize)

    result = get_views_insight(user_id, page_size=pageSize, page=page)
    items = result.get("items", [])

    for item in items:
        insight_id = item.get("insight_id")
        insight_content = get_insight_by_id(insight_id)
        if insight_content:
            _tmp = fill_nan(insight_content)
            item["insight"] = _tmp
            if "data_align" in _tmp:
                item["data"] = _tmp.get("data_align")

    out_data = [
        {
            "insight_id": item["insight_id"],
            "timestamp": item["timestamp"],
            "create_datetime": item["create_datetime"],
            "data": item.get("data"),
        }
        for item in items
    ]
    return out_data


@router.get("/{insightId}", summary="获取 Insight 详情")
async def get_insight_detail(
    insightId: str,
    fromFeed: bool = Query(False, description="是否来自 Feed 点击"),
    user: Dict[str, Any] = Depends(get_current_user),
):
    """
    获取单条 Insight 详情页内容。

    - `insightId`: Feed 接口返回的 ID
    - `fromFeed`: 标识是否来自 Feed 点击，用于后端埋点归因
    """
    detail = get_insight_by_id(insightId)
    if not detail:
        logger.warning("get_insight_detail: not found: insightId=%s", insightId)
        raise HTTPException(status_code=404, detail=f"Insight {insightId} not found")

    if fromFeed:
        logger.info("get_insight_detail: insightId=%s viewed from feed", insightId)

    out_data = detail.get("data_align")

    # 记录浏览历史
    user_id = user.get("username", "unknown")
    log_views_insight(user_id, insightId)

    logger.info("get_insight_detail: user_id=%s insightId=%s", user_id, insightId)
    return out_data


@router.get("/history/recommendations", summary="获取推荐历史")
async def get_recommendation_history(
    pageSize: int = Query(20, ge=1, le=100),
    page: int = Query(1, ge=1),
    action: Optional[str] = Query(None, description="过滤特定动作: click/dismiss/share/save"),
    user: Dict[str, Any] = Depends(get_current_user),
):
    """获取用户的推荐交互历史记录。"""
    user_id = user.get("username", "unknown")
    logger.info(
        "get_recommendation_history: user_id=%s page=%d pageSize=%d action=%s",
        user_id,
        page,
        pageSize,
        action,
    )

    try:
        result = get_recommendation_history_docs(
            user_id=user_id,
            page_size=pageSize,
            page=page,
            action=action,
        )
        return result
    except Exception as e:
        logger.exception("获取推荐历史失败: user_id=%s, error=%s", user_id, e)
        return {
            "items": [],
            "pagination": {
                "page": page,
                "pageSize": pageSize,
                "total": 0,
                "hasMore": False,
            },
        }
