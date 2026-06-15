"""
AI Insights 路由 - 市场洞察卡片 Feed 流

提供 AI 生成的市场洞察卡片流、详情页、风险披露等功能。
"""

import logging
import base64
import json
from typing import Optional, List
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Header, Request
from pydantic import BaseModel, Field

from app.core.db.document import (
    log_rec_history, log_rec_content_history, log_views_insight,
    get_views_insight, get_recommendation_history_docs,
    get_user_profile, get_rec_history, get_insight_by_id
)
from app.routers.auth_db import get_current_user

from tradingagents.searcher import VectorStore

logger = logging.getLogger("webapi")
router = APIRouter(prefix="/v1/ai-insights", tags=["AI Insights"])

# ============================================================================
# 常量与枚举
# ============================================================================

INSIGHT_TYPES = ["MACRO", "PORTFOLIO", "SECTOR", "DIVIDEND", "FIFTY_TWO_WEEK", "VOLATILITY", "POPULAR"]

TYPE_LABELS = {
    "MACRO": ("Macro & Micro", "宏觀與微觀經濟"),
    "PORTFOLIO": ("For You", "為您推薦"),
    "SECTOR": ("Sectors", "板塊"),
    "DIVIDEND": ("High Dividend", "高股息"),
    "FIFTY_TWO_WEEK": ("52-Week High/Low", "52週高低位"),
    "VOLATILITY": ("Big Movers", "大幅波動"),
    "POPULAR": ("Popular", "熱門話題"),
}


def get_tag_name(name_str):
    """
    获取tag
    Args:
        name_str:

    Returns:

    """
    from recommender.user_profile.gen_user_profiles import USER_PROFILE_TAGS
    if name_str in USER_PROFILE_TAGS:
        return USER_PROFILE_TAGS[name_str]
    return name_str


# ============================================================================
# API 接口
# ============================================================================

@router.get("/feed", summary="获取 AI Insights Feed 流")
async def get_feed(
        k: int = Query(3, ge=1, le=30, description="返回数据的天数（控制召回数量）"),
        # user: dict = Depends(get_current_user),
):
    """
    获取 AI 洞察卡片 Feed 流，用于首页 "HSBC AI: Market Insights for You" 模块。
    - `k`: 返回数据的天数（控制召回数量），默认 5，最大 30
    """

    user_id = "admin123"
    profile = get_user_profile(user_id)
    tags = profile["generatedTags"]

    tags_names = [i.get('tag') for i in tags]
    tags_zn = [get_tag_name(i) for i in tags_names]

    # 推荐历史
    history = get_rec_history(user_id)

    # 召回
    vector_store = VectorStore('insight_agg')

    result = []
    for tag in tags_zn:
        vector = vector_store.search(tag, top_k=k)
        result.extend(vector)

    dt_dict = {}
    for item in result:
        if item.metadata.get('article_id') in history:
            continue
        dt_dict[item.id] = item

    result = list(dt_dict.values())

    # 评分排序
    result_sorted = sorted(result, key=lambda x: x.score, reverse=True)

    result_sorted = result_sorted[:k]

    # 记录推荐历史
    rec_ids = [i.metadata.get("article_id") for i in result_sorted]
    data_rec_log = {
        'user_id': user_id,
        'rec_content_ids': rec_ids,
        'create_datetime': datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    }

    log_rec_history(data_rec_log)

    out_data = []
    for item in result_sorted:
        data = {
            # "id": item.id,
            "title": item.metadata.get('title'),
            "uuid": item.metadata.get('article_id'),
            'language': item.metadata.get('language'),
        }
        out_data.append(data)

    # 保存推荐内容的完整数据
    log_rec_content_history(user_id, out_data)

    return {
        "data": out_data,
        "count": len(out_data)
    }


@router.get("/views/history", summary="获取 Insight 浏览历史")
async def get_insight_views_history(
    pageSize: int = Query(20, ge=1, le=100),
    page: int = Query(1, ge=1),
    # user: dict = Depends(get_current_user),
):
    """
    获取用户的 Insight 浏览历史记录。
    """
    user_id = "admin123"
    result = get_views_insight(user_id, page_size=pageSize, page=page)
    items = result.get('items')

    for item in items:
        insight_id = item.get('insight_id')
        insight_content = get_insight_by_id(insight_id)
        if insight_content:
            item['insight'] = insight_content

    return result


@router.get("/{insightId}", summary="获取 Insight 详情")
async def get_insight_detail(
        insightId: str,
        fromFeed: bool = Query(False, description="是否来自 Feed 点击"),
        # user: dict = Depends(get_current_user),
):
    """
    获取单条 Insight 详情页内容。
    
    - `insightId`: Feed 接口返回的 ID
    - `fromFeed`: 标识是否来自 Feed 点击，用于后端埋点归因
    """
    detail = get_insight_by_id(insightId)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Insight {insightId} not found")

    # TODO: 埋点归因（fromFeed 参数）
    if fromFeed:
        logger.info(f"Insight {insightId} viewed from feed")

    out_data = detail.get('data_align')
    # 记录浏览历史
    user_id = "admin123"
    log_views_insight(user_id, insightId)

    return out_data


@router.get("/history/recommendations", summary="获取推荐历史")
async def get_recommendation_history(
        pageSize: int = Query(20, ge=1, le=100),
        page: int = Query(1, ge=1),
        action: Optional[str] = Query(None, description="过滤特定动作: click/dismiss/share/save"),
        # user: dict = Depends(get_current_user),
):
    """
    获取用户的推荐交互历史记录。
    """
    user_id = "admin123"
    try:
        result = get_recommendation_history_docs(
            user_id=user_id,
            page_size=pageSize,
            page=page,
            action=action
        )
        items = result.get('items')
        rec_content = items.get("rec_content_data")
        return rec_content
    except Exception as e:
        logger.error(f"获取推荐历史失败: {e}")
        return {"items": [], "pagination": {"page": page, "pageSize": pageSize, "total": 0, "hasMore": False}}
