"""
查询推荐 API 路由
提供基于向量的相似问题推荐功能
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.routers.auth_db import get_current_user
from app.core.database import get_mongo_db
from app.services.recommendation.recommend_query import (
    QueryRecommendationService,
    get_query_recommendation_service,
    QueryRecommendation,
    RecommendQueryRequest,
    RecommendQueryResponse,
)


# ==================== QA Pair 查询模型 ====================

class QAPairResponse(BaseModel):
    """QA Pair 查询响应"""
    uuid: str
    meta_data: str
    query: str
    answer: str

router = APIRouter(prefix="/recommend-query", tags=["查询推荐"])
logger = logging.getLogger("webapi")


# ==================== API 接口 ====================

@router.get("/", response_model=RecommendQueryResponse, summary="推荐相似问题(GET)")
async def recommend_similar_queries_get(
    q: str = Query(..., description="用户查询文本"),
    top_k: int = Query(5, ge=1, le=20, description="返回数量"),
    # user: dict = Depends(get_current_user)
):
    """
    推荐相似问题（GET 方式，方便浏览器测试）
    
    Example:
        GET /api/recommend-query/?q=摩根大通&top_k=3
    """
    try:
        service = get_query_recommendation_service()
        response = service.recommend_with_details(query=q, top_k=top_k)
        return response
    except Exception as e:
        logger.error(f"查询推荐失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询推荐失败: {str(e)}")


@router.get("/qa/{uuid}", response_model=QAPairResponse, summary="通过 UUID 查询 QA 对")
async def get_qa_pair_by_uuid(
    uuid: str,
    # user: dict = Depends(get_current_user)
):
    """
    通过 UUID 查询 MongoDB 中 qa_pair 集合的问答对
    
    Args:
        uuid: QA 对的唯一标识符
        
    Returns:
        QAPairResponse: 包含 uuid, meta_data, query, answer 的响应
        
    Example:
        GET /api/recommend-query/qa/cf229763ecd14f71a1b887a89149c869
        
        ```json
        {
            "uuid": "cf229763ecd14f71a1b887a89149c869",
            "meta_data": "JPM",
            "query": "摩根大通现在多少钱一股？",
            "answer": "摩根大通(JPM)当前股价约189.07元。"
        }
        ```
    """
    try:
        db = get_mongo_db()
        collection = db["qa_pair"]
        
        # 查询指定 uuid 的文档
        doc = await collection.find_one({"uuid": uuid})
        
        if not doc:
            raise HTTPException(status_code=404, detail=f"未找到 uuid={uuid} 的 QA 记录")
        
        # 移除 MongoDB 的 _id 字段，构建响应
        return QAPairResponse(
            uuid=doc["uuid"],
            meta_data=doc.get("meta_data", ""),
            query=doc.get("query", ""),
            answer=doc.get("answer", ""),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询 QA Pair 失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询 QA Pair 失败: {str(e)}")
