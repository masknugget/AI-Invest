"""
调仓管家路由

提供压力测试、持仓诊断、调仓方案生成及方案详情/逻辑/建议/FAQ 接口。
数据持久化统一通过 app.core.db.p_advisor 完成。
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.routers.auth_db import get_current_user
from app.core.db import p_advisor
from recommender.portfolio_advisor import qa as qa_module
from app.services.portfolio_advisor import advisor

logger = logging.getLogger("webapi")
router = APIRouter(prefix="/v1/rebalance", tags=["rebalance"])


# ============================================================================
# 请求模型
# ============================================================================

class CreatePlanRequest(BaseModel):
    """生成调仓方案请求体"""
    risk_level: str = Field(..., description="目标风险等级，如 R3")
    constraints: Optional[dict] = Field(default_factory=dict, description="调仓约束条件")


# ============================================================================
# 统一响应包装
# ============================================================================

def _success(data: dict, message: str = "ok") -> dict:
    """统一成功响应格式：匹配接口描述中的 {code, data}。"""
    return {"code": 200, "data": data, "message": message}


def _wrap_error(message: str, code: int = 1) -> dict:
    """统一错误响应格式。"""
    return {"code": code, "data": None, "message": message}


def _get_user_id(user: Optional[dict] = None) -> str:
    """获取用户ID。当前默认 admin123，登录后可从 user 对象提取。"""
    if user and isinstance(user, dict) and user.get("user_id"):
        return str(user["user_id"])
    return "admin123"


# ============================================================================
# 调仓管家接口（前缀 /api/v1/rebalance）
# ============================================================================

@router.get("/stress-test", summary="压力测试")
async def rebalance_stress_test(
    scenario: Optional[str] = Query(None, description="压力场景 ID，如 2008_financial_crisis"),
    # user: dict = Depends(get_current_user)
):
    """
    历史极端行情下组合回撤模拟。

    优先返回数据库中保存的最新压力测试报告；若不存在，则生成新数据并保存。
    """
    user_id = _get_user_id()
    try:
        # 优先查询最新已保存的报告
        data = p_advisor.get_stress_report(user_id=user_id)
        if not data:
            data = advisor.get_stress_test(scenario=scenario)
            p_advisor.save_stress_report(data, user_id=user_id)
        return _success(data, "获取压力测试数据成功")
    except Exception as e:
        logger.error(f"❌ 获取压力测试数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/plan", summary="生成调仓方案")
async def rebalance_create_plan(
    request: CreatePlanRequest,
    # user: dict = Depends(get_current_user)
):
    """
    AI 计算优化后的配置方案。

    生成方案后保存到 p_advisor_rebalance_plans，并返回方案数据。
    """
    user_id = _get_user_id()
    try:
        summary = advisor.create_plan(
            risk_level=request.risk_level,
            constraints=request.constraints
        )

        # 包装成 rebalance_plans 格式并持久化
        formatted_plans = [
            {
                "plan_id": summary.get("plan_id"),
                "status": summary.get("status"),
                "created_at": summary.get("created_at"),
                "input": summary.get("input", {}),
                "summary": summary,
            }
        ]
        p_advisor.save_rebalance_plans(formatted_plans, user_id=user_id)

        return _success(summary, "生成调仓方案成功")
    except Exception as e:
        logger.error(f"❌ 生成调仓方案失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/plan/latest", summary="查询最新调仓方案")
async def rebalance_get_latest_plan(
    # user: dict = Depends(get_current_user)
):
    """查询用户最新保存的调仓方案列表。"""
    user_id = _get_user_id()
    try:
        plans = p_advisor.get_rebalance_plans(user_id=user_id)
        if not plans:
            return _success({"plans": []}, "暂无调仓方案")
        return _success({"plans": plans}, "获取最新调仓方案成功")
    except Exception as e:
        logger.error(f"❌ 查询最新调仓方案失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stress-report/latest", summary="查询最新压力测试报告")
async def rebalance_get_latest_stress_report(
    # user: dict = Depends(get_current_user)
):
    """查询用户最新保存的压力测试报告。"""
    user_id = _get_user_id()
    try:
        report = p_advisor.get_stress_report(user_id=user_id)
        if not report:
            return _success({"report": {}}, "暂无压力测试报告")
        return _success({"report": report}, "获取最新压力测试报告成功")
    except Exception as e:
        logger.error(f"❌ 查询最新压力测试报告失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/faq", summary="常用问题")
async def rebalance_faq(
    # user: dict = Depends(get_current_user)
):
    """获取投资组合/基金常用问题（FAQ），首次访问时从 qa.py 写入数据库。"""
    user_id = _get_user_id()
    try:
        faq = p_advisor.get_faq(user_id=user_id)
        if not faq:
            p_advisor.save_faq(qa_module.faq, user_id=user_id)
            faq = p_advisor.get_faq(user_id=user_id)
        data = {"faq": faq}
        return _success(data, "获取常用问题成功")
    except Exception as e:
        logger.error(f"❌ 获取常用问题失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
