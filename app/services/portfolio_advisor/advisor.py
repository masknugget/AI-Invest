"""
AI 调仓管家服务（初步实现）

基于 mock 数据提供压力测试、持仓诊断、调仓方案生成、方案详情、
调仓逻辑与实施建议等骨架实现。
"""

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MOCK_DIR = PROJECT_ROOT / "mock" / "rebalance"


def _load_mock_json(filename: str) -> Dict[str, Any]:
    """加载指定 mock JSON 文件。"""
    file_path = MOCK_DIR / filename
    if not file_path.exists():
        return {}
    with file_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _now_str() -> str:
    """返回当前 UTC 时间的 ISO 格式字符串。"""
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _generate_plan_id() -> str:
    """生成调仓方案 ID。"""
    dt = datetime.utcnow().strftime("%Y%m%d")
    suffix = uuid.uuid4().hex[:3].upper()
    return f"PLAN_{dt}_{suffix}"


# ============================================================================
# 1. 压力测试
# ============================================================================

def get_stress_test(scenario: Optional[str] = None) -> Dict[str, Any]:
    """
    获取指定压力测试场景下的组合回撤数据。

    Args:
        scenario: 场景 ID，如 2008_financial_crisis；不传则使用默认场景。

    Returns:
        压力测试结果
    """
    data = _load_mock_json("stress_test.json")
    scenario_list = data.get("scenario_list", [])

    # 若指定了场景且场景存在，则替换当前 scenario
    selected = None
    if scenario:
        selected = next((s for s in scenario_list if s.get("id") == scenario), None)
    if not selected:
        selected = next((s for s in scenario_list if s.get("is_default")), scenario_list[0] if scenario_list else {})

    data["scenario"] = selected
    return data


# ============================================================================
# 2. 持仓诊断
# ============================================================================

def get_diagnosis() -> Dict[str, Any]:
    """获取当前持仓诊断数据。"""
    return _load_mock_json("diagnosis.json")


# ============================================================================
# 3. 生成调仓方案
# ============================================================================

def create_plan(
    risk_level: str,
    constraints: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    生成调仓方案（mock 实现，仅返回固定优化指标与新生成的 plan_id）。

    Args:
        risk_level: 用户目标风险等级，如 R3
        constraints: 调仓约束条件

    Returns:
        方案摘要
    """
    summary = _load_mock_json("plan_summary.json")
    summary["plan_id"] = _generate_plan_id()
    summary["status"] = "generated"
    summary["created_at"] = _now_str()
    summary["input"] = {
        "risk_level": risk_level,
        "constraints": constraints or {}
    }
    return summary


# ============================================================================
# 4. 方案详情
# ============================================================================

def get_plan_detail(plan_id: str) -> Dict[str, Any]:
    """
    获取指定方案的买卖明细。

    Args:
        plan_id: 方案 ID

    Returns:
        方案详情
    """
    data = _load_mock_json("plan_detail.json")
    data["plan_id"] = plan_id
    return data


# ============================================================================
# 5. 调仓逻辑
# ============================================================================

def get_plan_logic(plan_id: str) -> Dict[str, Any]:
    """
    获取指定方案的三大策略解释。

    Args:
        plan_id: 方案 ID

    Returns:
        调仓逻辑
    """
    data = _load_mock_json("plan_logic.json")
    data["plan_id"] = plan_id
    return data


# ============================================================================
# 6. 实施建议
# ============================================================================

def get_plan_tips(plan_id: str) -> Dict[str, Any]:
    """
    获取指定方案的新手建议与 FAQ。

    Args:
        plan_id: 方案 ID

    Returns:
        实施建议
    """
    data = _load_mock_json("plan_tips.json")
    data["plan_id"] = plan_id
    return data
