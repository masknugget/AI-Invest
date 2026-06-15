"""
投资组合风险诊断路由（初步实现）

提供账户健康度、五维能力、风险提示、行业分布、分享与 AI 优化方案接口。
所有数据当前来自 mock/risk_diagnosis/ 下的静态 JSON，仅作骨架演示。
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.routers.auth_db import get_current_user
from app.services.portfolio_advisor import risk_profile, advisor

logger = logging.getLogger("webapi")
router = APIRouter(prefix="/risk/diagnosis", tags=["risk-diagnosis"])

# 调仓管家路由（独立前缀 /api/v1/rebalance）
rebalance_router = APIRouter(prefix="/v1/rebalance", tags=["rebalance"])


# ============================================================================
# 请求模型
# ============================================================================

class ReportQuery(BaseModel):
    """综合账户健康度查询参数"""
    user_id: str = Field(..., description="用户标识")
    account_type: Optional[str] = Field(None, description="账户类型：fund/stock/all")
    diagnosis_date: Optional[str] = Field(None, description="诊断日期，默认最新")


class RiskAlertsQuery(BaseModel):
    """风险提示查询参数"""
    user_id: str = Field(..., description="用户标识")
    severity: Optional[str] = Field("all", description="过滤：all/high/medium/low")


class IndustryDistQuery(BaseModel):
    """行业分布查询参数"""
    user_id: str = Field(..., description="用户标识")
    top_n: int = Field(5, ge=1, le=20, description="返回前N个行业，其余归入'其他'")


class ShareRequest(BaseModel):
    """分享功能请求体"""
    user_id: str = Field(..., description="用户标识")
    share_type: str = Field(..., description="分享类型：poster/link/wechat")
    content_scope: str = Field(..., description="分享内容范围：summary/full")
    custom_text: Optional[str] = Field(None, description="用户自定义文案")


class AiSolutionQuery(BaseModel):
    """AI 优化方案查询参数"""
    user_id: str = Field(..., description="用户标识")
    scenario: Optional[str] = Field("risk_optimization", description="场景：risk_optimization/rebalance/goal_based")


class CreatePlanRequest(BaseModel):
    """生成调仓方案请求体"""
    risk_level: str = Field(..., description="目标风险等级，如 R3")
    constraints: Optional[dict] = Field(default_factory=dict, description="调仓约束条件")


# ============================================================================
# 统一响应包装
# ============================================================================

def _success(data: dict, message: str = "ok") -> dict:
    """统一成功响应格式：匹配接口描述中的 {code, data}。"""
    return {"code": 0, "data": data, "message": message}


def _wrap_error(message: str, code: int = 1) -> dict:
    """统一错误响应格式。"""
    return {"code": code, "data": None, "message": message}


# ============================================================================
# API 接口
# ============================================================================

@router.get("/report", summary="综合账户健康度")
async def get_report(
    user_id: str = Query(..., description="用户标识"),
    account_type: Optional[str] = Query(None, description="账户类型：fund/stock/all"),
    diagnosis_date: Optional[str] = Query(None, description="诊断日期，默认最新"),
    user: dict = Depends(get_current_user)
):
    """聚合返回评分、评级、评语及历史评分趋势。"""
    try:
        data = risk_profile.get_risk_report(
            user_id=user_id,
            account_type=account_type,
            diagnosis_date=diagnosis_date
        )
        return _success(data, "获取账户健康度成功")
    except Exception as e:
        logger.error(f"❌ 获取账户健康度失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dimensions", summary="五维能力透视（雷达图）")
async def get_dimensions(
    user_id: str = Query(..., description="用户标识"),
    user: dict = Depends(get_current_user)
):
    """返回收益稳定性、风格均衡、持仓性价比、抗回撤能力、行业分散度五维评分。"""
    try:
        data = risk_profile.get_dimensions(user_id=user_id)
        return _success(data, "获取五维评分成功")
    except Exception as e:
        logger.error(f"❌ 获取五维评分失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/risk-alerts", summary="核心风险提示")
async def get_risk_alerts(
    user_id: str = Query(..., description="用户标识"),
    severity: Optional[str] = Query("all", description="过滤：all/high/medium/low"),
    user: dict = Depends(get_current_user)
):
    """返回风险清单及详情，支持按严重程度过滤。"""
    try:
        data = risk_profile.get_risk_alerts(user_id=user_id, severity=severity)
        return _success(data, "获取风险提示成功")
    except Exception as e:
        logger.error(f"❌ 获取风险提示失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/industry-dist", summary="行业分布地图")
async def get_industry_distribution(
    user_id: str = Query(..., description="用户标识"),
    top_n: int = Query(5, ge=1, le=20, description="返回前N个行业，其余归入'其他'"),
    user: dict = Depends(get_current_user)
):
    """返回行业占比分布，支持合并剩余行业为"其他"。"""
    try:
        data = risk_profile.get_industry_distribution(user_id=user_id, top_n=top_n)
        return _success(data, "获取行业分布成功")
    except Exception as e:
        logger.error(f"❌ 获取行业分布失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/share", summary="分享功能")
async def create_share(
    request: ShareRequest,
    user: dict = Depends(get_current_user)
):
    """生成分享海报/链接/微信小程序卡片。"""
    try:
        data = risk_profile.create_share(
            user_id=request.user_id,
            share_type=request.share_type,
            content_scope=request.content_scope,
            custom_text=request.custom_text
        )
        return _success(data, "生成分享内容成功")
    except Exception as e:
        logger.error(f"❌ 生成分享内容失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ai-solution", summary="AI 优化方案入口")
async def get_ai_solution(
    user_id: str = Query(..., description="用户标识"),
    scenario: Optional[str] = Query("risk_optimization", description="场景：risk_optimization/rebalance/goal_based"),
    user: dict = Depends(get_current_user)
):
    """返回 AI 优化建议摘要、预期效果与具体调仓动作。"""
    try:
        data = risk_profile.get_ai_solution(user_id=user_id, scenario=scenario)
        return _success(data, "获取 AI 优化方案成功")
    except Exception as e:
        logger.error(f"❌ 获取 AI 优化方案失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/overview", summary="风险诊断聚合接口")
async def get_overview(
    user_id: str = Query(..., description="用户标识"),
    user: dict = Depends(get_current_user)
):
    """聚合返回 report / dimensions / risk_alerts / industry_dist，减少移动端请求数。"""
    try:
        data = risk_profile.get_overview(user_id=user_id)
        return _success(data, "获取风险诊断聚合数据成功")
    except Exception as e:
        logger.error(f"❌ 获取风险诊断聚合数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# 调仓管家接口（前缀 /api/v1/rebalance）
# ============================================================================

@rebalance_router.get("/stress-test", summary="压力测试")
async def rebalance_stress_test(
    scenario: Optional[str] = Query(None, description="压力场景 ID，如 2008_financial_crisis"),
    user: dict = Depends(get_current_user)
):
    """历史极端行情下组合回撤模拟。"""
    try:
        data = advisor.get_stress_test(scenario=scenario)
        return _success(data, "获取压力测试数据成功")
    except Exception as e:
        logger.error(f"❌ 获取压力测试数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@rebalance_router.get("/diagnosis", summary="持仓诊断")
async def rebalance_diagnosis(
    user: dict = Depends(get_current_user)
):
    """当前组合收益、波动率与风险画像。"""
    try:
        data = advisor.get_diagnosis()
        return _success(data, "获取持仓诊断成功")
    except Exception as e:
        logger.error(f"❌ 获取持仓诊断失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@rebalance_router.post("/plan", summary="生成调仓方案")
async def rebalance_create_plan(
    request: CreatePlanRequest,
    user: dict = Depends(get_current_user)
):
    """AI 计算优化后的配置方案。"""
    try:
        data = advisor.create_plan(
            risk_level=request.risk_level,
            constraints=request.constraints
        )
        return _success(data, "生成调仓方案成功")
    except Exception as e:
        logger.error(f"❌ 生成调仓方案失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@rebalance_router.get("/plan/{plan_id}", summary="方案详情")
async def rebalance_plan_detail(
    plan_id: str,
    user: dict = Depends(get_current_user)
):
    """调仓方案买卖明细清单。"""
    try:
        data = advisor.get_plan_detail(plan_id=plan_id)
        return _success(data, "获取方案详情成功")
    except Exception as e:
        logger.error(f"❌ 获取方案详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@rebalance_router.get("/plan/{plan_id}/logic", summary="调仓逻辑")
async def rebalance_plan_logic(
    plan_id: str,
    user: dict = Depends(get_current_user)
):
    """调仓方案三大策略解释。"""
    try:
        data = advisor.get_plan_logic(plan_id=plan_id)
        return _success(data, "获取调仓逻辑成功")
    except Exception as e:
        logger.error(f"❌ 获取调仓逻辑失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@rebalance_router.get("/plan/{plan_id}/tips", summary="实施建议")
async def rebalance_plan_tips(
    plan_id: str,
    user: dict = Depends(get_current_user)
):
    """新手操作指引与 FAQ。"""
    try:
        data = advisor.get_plan_tips(plan_id=plan_id)
        return _success(data, "获取实施建议成功")
    except Exception as e:
        logger.error(f"❌ 获取实施建议失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
