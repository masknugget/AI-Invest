"""
投资组合风险诊断路由

提供账户健康度、五维能力、风险提示、行业分布与 AI 优化方案接口。
数据通过 app.core.db.p_advisor 从 MongoDB 读写。
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.routers.auth_db import get_current_user
from app.core.db import p_advisor

logger = logging.getLogger("webapi")
router = APIRouter(prefix="/v1/diagnosis", tags=["risk-diagnosis"])


# ============================================================================
# 请求模型
# ============================================================================

class ReportQuery(BaseModel):
    """综合账户健康度查询参数"""
    account_type: Optional[str] = Field(None, description="账户类型：fund/stock/all")
    diagnosis_date: Optional[str] = Field(None, description="诊断日期，默认最新")


class RiskAlertsQuery(BaseModel):
    """风险提示查询参数"""
    severity: Optional[str] = Field("all", description="过滤：all/high/medium/low")


class IndustryDistQuery(BaseModel):
    """行业分布查询参数"""
    top_n: int = Field(5, ge=1, le=20, description="返回前N个行业，其余归入'其他'")


class AiSolutionQuery(BaseModel):
    """AI 优化方案查询参数"""
    scenario: Optional[str] = Field("risk_optimization", description="场景：risk_optimization/rebalance/goal_based")


# ============================================================================
# 统一响应包装
# ============================================================================

def _success(data: dict, message: str = "ok") -> dict:
    """统一成功响应格式：匹配接口描述中的 {code, data}。"""
    return {"code": 200, "data": data, "message": message}


def _wrap_error(message: str, code: int = 1) -> dict:
    """统一错误响应格式。"""
    return {"code": code, "data": None, "message": message}


# ============================================================================
# API 接口
# ============================================================================

@router.get("/report", summary="综合账户健康度")
async def get_report(
    account_type: Optional[str] = Query(None, description="账户类型：fund/stock/all"),
    diagnosis_date: Optional[str] = Query(None, description="诊断日期，默认最新"),
    # user: dict = Depends(get_current_user)
):
    """聚合返回评分、评级、评语及历史评分趋势。"""
    user_id = 'admin123'
    try:
        data = p_advisor.get_risk_report(
            user_id=user_id,
            account_type=account_type,
            diagnosis_date=diagnosis_date,
        ) or {}
        data.setdefault("user_id", user_id)
        return _success(data, "获取账户健康度成功")
    except Exception as e:
        logger.error(f"❌ 获取账户健康度失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dimensions", summary="五维能力透视（雷达图）")
async def get_dimensions(
    # user: dict = Depends(get_current_user)
):
    """返回收益稳定性、风格均衡、持仓性价比、抗回撤能力、行业分散度五维评分。"""

    user_id = 'admin123'
    try:
        data = p_advisor.get_latest_dimensions(user_id=user_id)
        data.setdefault("user_id", user_id)
        return _success(data, "获取五维评分成功")
    except Exception as e:
        logger.error(f"❌ 获取五维评分失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/risk-alerts", summary="核心风险提示")
async def get_risk_alerts(
    severity: Optional[str] = Query("all", description="过滤：all/high/medium/low"),
    # user: dict = Depends(get_current_user)
):
    """返回风险清单及详情，支持按严重程度过滤。"""
    user_id = "admin123"
    try:
        data = p_advisor.get_risk_alert(
            user_id=user_id,
            severity=severity,
        ) or {}
        data.setdefault("user_id", user_id)
        return _success(data, "获取风险提示成功")
    except Exception as e:
        logger.error(f"❌ 获取风险提示失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/industry-dist", summary="行业分布地图")
async def get_industry_distribution(
    top_n: int = Query(5, ge=1, le=20, description="返回前N个行业，其余归入'其他'"),
    # user: dict = Depends(get_current_user)
):
    """返回行业占比分布，支持合并剩余行业为"其他"。"""
    user_id = "admin123"
    try:
        data = p_advisor.get_industry_distribution(
            user_id=user_id,
            top_n=top_n,
        ) or {}
        data.setdefault("user_id", user_id)
        return _success(data, "获取行业分布成功")
    except Exception as e:
        logger.error(f"❌ 获取行业分布失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ai-solution", summary="AI 优化方案入口")
async def get_ai_solution(
    scenario: Optional[str] = Query("risk_optimization", description="场景：risk_optimization/rebalance/goal_based"),
    user: dict = Depends(get_current_user)
):
    """返回 AI 优化建议摘要、预期效果与具体调仓动作。"""
    user_id = "admin123"
    try:
        data = p_advisor.get_ai_solution(
            user_id=user_id,
            scenario=scenario or "risk_optimization",
        )
        return _success(data, "获取 AI 优化方案成功")
    except Exception as e:
        logger.error(f"❌ 获取 AI 优化方案失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/overview", summary="风险诊断聚合接口")
async def get_overview(
    user: dict = Depends(get_current_user)
):
    """聚合返回 report / dimensions / risk_alerts / industry_dist，减少移动端请求数。"""
    user_id = "admin123"
    try:
        data = p_advisor.get_overview(user_id=user_id)
        return _success(data, "获取风险诊断聚合数据成功")
    except Exception as e:
        logger.error(f"❌ 获取风险诊断聚合数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
