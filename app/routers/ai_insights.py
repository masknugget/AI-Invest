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

from app.core.db.document import log_rec_history, get_user_profile, get_rec_history
from app.routers.auth_db import get_current_user
from app.core.database import get_mongo_db
from scripts.data_handler.news.prompt_userprofiles import USER_PROFILE_TAGS
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

DISCLOSURE_VERSION = "2026-04-v1"




def get_tag_name(name_str):
    """
    获取tag
    Args:
        name_str:

    Returns:

    """
    if name_str in USER_PROFILE_TAGS:
        return USER_PROFILE_TAGS[name_str]
    return name_str



# ============================================================================
# API 接口
# ============================================================================

@router.get("/feed", summary="获取 AI Insights Feed 流")
async def get_feed(
        pageSize: int = Query(5, ge=1, le=20, description="单次拉取数量"),
        cursor: Optional[str] = Query(None, description="分页游标"),
        filterTypes: Optional[str] = Query(None, description="逗号分隔的内容类型过滤，如 MACRO,SECTOR,VOLATILITY"),
        # user: dict = Depends(get_current_user),
):
    """
    获取 AI 洞察卡片 Feed 流，用于首页 "HSBC AI: Market Insights for You" 模块。
    
    - `pageSize`: 单次拉取数量，默认 5，最大 20
    - `cursor`: 分页游标，首次请求为空，翻页时传入上次响应的 nextCursor
    - `filterTypes`: 逗号分隔的内容类型过滤
    """


    user_id = "admin123"
    profile = get_user_profile(user_id)
    tags = profile["generatedTags"]

    tags_names = [i.get('tag') for i in tags]
    tags_zn = [get_tag_name(i) for i in tags_names]

    # 推荐历史
    history = get_rec_history(user_id)

    # 召回
    vector_store = VectorStore('insight_news')

    result = []
    for tag in tags_zn:
        vector = vector_store.search(tag, top_k=5)
        result.extend(vector)

    dt_dict = {}
    for item in result:
        if item.id in history:
            continue
        dt_dict[item.id] = item

    result = list(dt_dict.values())

    # 评分排序
    result_sorted = sorted(result, key=lambda x: x.score, reverse=True)

    result_sorted = result_sorted[:3]

    # 记录推荐历史
    rec_ids = [i.id for i in result_sorted]
    data_rec_log = {
        'user_id': user_id,
        'rec_content_ids': rec_ids,
        'create_datetime': datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    }

    log_rec_history(data_rec_log)

    return {

    }

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
    detail = _mock_insight_detail(insightId)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Insight {insightId} not found")

    # TODO: 埋点归因（fromFeed 参数）
    if fromFeed:
        logger.info(f"Insight {insightId} viewed from feed")

    return detail




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
    try:
        db = get_mongo_db()
        collection = db["ai_insights_recommendation_logs"]

        # 构建查询条件
        query = {}
        # query["userId"] = user.get("id")
        if action:
            query["action"] = action

        # 分页查询
        skip = (page - 1) * pageSize
        cursor = collection.find(query).sort("timestamp", -1).skip(skip).limit(pageSize)
        items = await cursor.to_list(length=pageSize)

        # 清理 MongoDB _id
        for item in items:
            item.pop("_id", None)

        # 获取总数
        total = await collection.count_documents(query)

        return {
            "items": items,
            "pagination": {
                "page": page,
                "pageSize": pageSize,
                "total": total,
                "hasMore": total > skip + len(items),
            }
        }

    except Exception as e:
        logger.error(f"获取推荐历史失败: {e}")
        return {"items": [], "pagination": {"page": page, "pageSize": pageSize, "total": 0, "hasMore": False}}


# ============================================================================
# 浏览记录
# ============================================================================

@router.post("/track/view", summary="记录浏览行为")
async def track_view(
        request: TrackViewRequest,
        # user: dict = Depends(get_current_user),
):
    """
    记录用户的浏览行为（阅读时长、滚动深度等）。
    
    用于分析用户对内容的兴趣度和优化内容推荐。
    """
    try:
        db = get_mongo_db()
        collection = db["ai_insights_view_logs"]

        record = {
            # "userId": user.get("id"),
            "insightId": request.insightId,
            "durationSeconds": request.durationSeconds,
            "scrollDepth": request.scrollDepth,
            "timestamp": request.timestamp or _now_iso(),
            "createdAt": _now_iso(),
        }

        await collection.insert_one(record)

        logger.info(f"浏览记录: insightId={request.insightId}, duration={request.durationSeconds}s")

        return {"success": True, "message": "记录已保存"}

    except Exception as e:
        logger.error(f"记录浏览行为失败: {e}")
        return {"success": True, "message": "记录已接收"}


@router.get("/history/views", summary="获取浏览历史")
async def get_view_history(
        pageSize: int = Query(20, ge=1, le=100),
        page: int = Query(1, ge=1),
        # user: dict = Depends(get_current_user),
):
    """
    获取用户的浏览历史记录。
    """
    try:
        db = get_mongo_db()
        collection = db["ai_insights_view_logs"]

        # 构建查询条件
        query = {}
        # query["userId"] = user.get("id")

        # 分页查询
        skip = (page - 1) * pageSize
        cursor = collection.find(query).sort("timestamp", -1).skip(skip).limit(pageSize)
        items = await cursor.to_list(length=pageSize)

        # 清理 MongoDB _id
        for item in items:
            item.pop("_id", None)

        # 获取总数
        total = await collection.count_documents(query)

        return {
            "items": items,
            "pagination": {
                "page": page,
                "pageSize": pageSize,
                "total": total,
                "hasMore": total > skip + len(items),
            }
        }

    except Exception as e:
        logger.error(f"获取浏览历史失败: {e}")
        return {"items": [], "pagination": {"page": page, "pageSize": pageSize, "total": 0, "hasMore": False}}
