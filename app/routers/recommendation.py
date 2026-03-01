"""
推荐服务 API 路由 - 简化版

提供基础的股票推荐功能，无需用户画像
"""

from typing import Optional, List
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks

from app.routers.auth_db import get_current_user
from app.models.recommendation import (
    RecommendationQuery,
    BatchGenerateRequest,
    RiskLevel,
)
from app.services.recommendation import get_recommendation_service
from app.core.response import ok as success_response

router = APIRouter(prefix="/recommendations", tags=["recommendations"])
logger = logging.getLogger(__name__)


@router.get("/stocks", response_model=dict)
async def get_stock_recommendations(
    top_k: int = Query(default=10, ge=1, le=50, description="返回数量"),
    skip: int = Query(default=0, ge=0, description="跳过数量（用于分页）"),
    exclude_viewed: bool = Query(default=True, description="是否排除已查看的"),
    date: Optional[str] = Query(default=None, description="日期(YYYY-MM-DD)"),
    risk_level: Optional[RiskLevel] = Query(default=None, description="风险等级筛选"),
    industries: Optional[List[str]] = Query(default=None, description="行业筛选"),
    min_score: Optional[float] = Query(default=None, ge=0, le=100, description="最低评分"),
    current_user: dict = Depends(get_current_user),
):
    """
    获取股票推荐列表（支持筛选、分页、去重）
    
    支持:
    - 按风险等级、行业、评分等条件筛选
    - 分页加载（skip + top_k）
    - 自动排除已查看的推荐（exclude_viewed=true）
    """
    try:
        query = RecommendationQuery(
            top_k=top_k,
            skip=skip,
            exclude_viewed=exclude_viewed,
            date=date,
            risk_level=risk_level,
            industries=industries,
            min_score=min_score,
        )
        
        service = get_recommendation_service()
        result = await service.get_recommendations_by_filter(
            query, 
            user_id=str(current_user["id"]) if exclude_viewed else None
        )
        return success_response(data=result)
    except Exception as e:
        logger.error(f"获取推荐列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stocks/{symbol}", response_model=dict)
async def get_stock_recommendation_detail(
    symbol: str,
    date: Optional[str] = Query(default=None, description="日期(YYYY-MM-DD)"),
    current_user: dict = Depends(get_current_user),
):
    """
    获取单只股票的推荐详情
    
    包括评分、风险等级、推荐理由等详细信息
    """
    try:
        service = get_recommendation_service()
        result = await service.get_stock_recommendation(symbol, date)
        
        if result is None:
            raise HTTPException(status_code=404, detail=f"未找到股票 {symbol} 的推荐数据")
        
        return success_response(data=result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取股票推荐详情失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard", response_model=dict)
async def get_dashboard(
    current_user: dict = Depends(get_current_user),
):
    """
    获取推荐仪表盘数据
    
    包括热门股票、统计数据等
    """
    try:
        service = get_recommendation_service()
        result = await service.get_dashboard_data()
        
        if result is None:
            return success_response(data=None, message="暂无推荐数据")
        
        return success_response(data=result)
    except Exception as e:
        logger.error(f"获取仪表盘数据失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=dict)
async def get_recommendation_stats(
    date: Optional[str] = Query(default=None, description="日期(YYYY-MM-DD)"),
    current_user: dict = Depends(get_current_user),
):
    """
    获取推荐数据统计
    
    包括推荐等级分布、风险等级分布等
    """
    try:
        service = get_recommendation_service()
        result = await service.get_stats(date)
        
        if result is None:
            return success_response(data=None, message="暂无统计数据")
        
        return success_response(data=result)
    except Exception as e:
        logger.error(f"获取统计数据失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/batch-generate", response_model=dict)
async def trigger_batch_generation(
    request: BatchGenerateRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """
    手动触发推荐数据批量生成（管理员功能）
    
    通常在每天凌晨自动执行，此处供手动触发测试用
    """
    try:
        # 检查用户权限（简单检查，实际应用应该使用更完善的权限系统）
        if not current_user.get("is_admin", False):
            raise HTTPException(status_code=403, detail="需要管理员权限")
        
        service = get_recommendation_service()
        
        # 在后台执行
        async def run_batch():
            await service.trigger_batch_generation(request.max_stocks)
        
        background_tasks.add_task(run_batch)
        
        return success_response(
            message="批处理任务已在后台启动",
            data={"status": "processing"}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"触发批处理失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/latest-date", response_model=dict)
async def get_latest_recommendation_date(
    current_user: dict = Depends(get_current_user),
):
    """
    获取最新推荐数据的日期
    """
    try:
        service = get_recommendation_service()
        date = service._get_latest_date()
        
        if date is None:
            return success_response(data=None, message="暂无推荐数据")
        
        return success_response(data={"latest_date": date})
    except Exception as e:
        logger.error(f"获取最新日期失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 推荐历史接口 ====================

@router.post("/view/{symbol}", response_model=dict)
async def record_recommendation_view(
    symbol: str,
    date: Optional[str] = Query(default=None, description="推荐数据日期"),
    current_user: dict = Depends(get_current_user),
):
    """
    记录用户查看了某只股票的推荐
    
    用于去重和生成推荐历史
    """
    try:
        profile_service = get_user_profile_service()
        
        # 获取当前推荐日期
        if date is None:
            rec_service = get_recommendation_service()
            date = rec_service._get_latest_date()
        
        await profile_service.record_view(
            user_id=str(current_user["id"]),
            symbol=symbol,
            recommendation_date=date or datetime.now().strftime("%Y-%m-%d")
        )
        
        return success_response(message="已记录查看")
    except Exception as e:
        logger.error(f"记录查看失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", response_model=dict)
async def get_recommendation_history(
    skip: int = Query(default=0, ge=0, description="跳过数量"),
    limit: int = Query(default=20, ge=1, le=100, description="返回数量"),
    current_user: dict = Depends(get_current_user),
):
    """
    获取用户的推荐查看历史
    
    按时间倒序返回用户查看过的推荐记录
    """
    try:
        profile_service = get_user_profile_service()
        
        history = await profile_service.get_recommendation_history(
            user_id=str(current_user["id"]),
            skip=skip,
            limit=limit
        )
        
        return success_response(data={
            "total": len(history),
            "skip": skip,
            "history": history
        })
    except Exception as e:
        logger.error(f"获取推荐历史失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/history", response_model=dict)
async def clear_recommendation_history(
    current_user: dict = Depends(get_current_user),
):
    """
    清空用户的推荐历史
    
    清空后，之前的推荐可能再次出现在列表中
    """
    try:
        profile_service = get_user_profile_service()
        
        success = await profile_service.clear_history(str(current_user["id"]))
        
        if success:
            return success_response(message="推荐历史已清空")
        else:
            return success_response(message="没有可清空的历史记录")
    except Exception as e:
        logger.error(f"清空推荐历史失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
