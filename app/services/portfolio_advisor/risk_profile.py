"""
投资组合风险画像服务（初步实现）

基于 mock 数据提供账户健康度、五维评分、风险提示、行业分布、
分享功能与 AI 优化方案的骨架实现。
"""

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# mock 数据目录：项目根目录 / mock / risk_diagnosis
PROJECT_ROOT = Path(__file__).resolve().parents[3]
MOCK_DIR = PROJECT_ROOT / "mock" / "risk_diagnosis"


def _load_mock_json(filename: str) -> Dict[str, Any]:
    """加载指定 mock JSON 文件。"""
    file_path = MOCK_DIR / filename
    if not file_path.exists():
        return {}
    with file_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _now_str() -> str:
    """返回当前时间的字符串表示（UTC+8）。"""
    return (datetime.utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")


def get_risk_report(
    user_id: str,
    account_type: Optional[str] = None,
    diagnosis_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    获取综合账户健康度报告。

    Args:
        user_id: 用户标识
        account_type: 账户类型 fund/stock/all（可选）
        diagnosis_date: 诊断日期，默认最新（可选）

    Returns:
        账户健康度报告数据
    """
    data = _load_mock_json("report.json")
    # 使用请求参数简单覆盖，便于前端调试不同场景
    if account_type:
        data["account_type"] = account_type
    if diagnosis_date:
        data["diagnosis_date"] = diagnosis_date
    data.setdefault("user_id", user_id)
    data.setdefault("update_time", _now_str())
    return data


def get_dimensions(user_id: str) -> Dict[str, Any]:
    """
    获取五维能力透视（雷达图）数据。

    Args:
        user_id: 用户标识

    Returns:
        五维评分与基准数据
    """
    data = _load_mock_json("dimensions.json")
    data.setdefault("user_id", user_id)
    return data


def get_risk_alerts(user_id: str, severity: Optional[str] = "all") -> Dict[str, Any]:
    """
    获取核心风险提示清单。

    Args:
        user_id: 用户标识
        severity: 风险等级过滤 all/high/medium/low

    Returns:
        风险清单及详情
    """
    data = _load_mock_json("risk_alerts.json")
    alerts: List[Dict[str, Any]] = data.get("alerts", [])

    if severity and severity.lower() != "all":
        alerts = [a for a in alerts if a.get("severity") == severity.lower()]

    data["alerts"] = alerts
    data["total_count"] = len(alerts)
    data.setdefault("user_id", user_id)
    return data


def get_industry_distribution(user_id: str, top_n: int = 5) -> Dict[str, Any]:
    """
    获取行业分布地图数据。

    Args:
        user_id: 用户标识
        top_n: 返回前 N 个行业，其余归入"其他"

    Returns:
        行业占比分布
    """
    data = _load_mock_json("industry_dist.json")
    industries: List[Dict[str, Any]] = data.get("industries", [])

    # 按占比降序排序，top_n 以外的合并为"其他"
    industries = sorted(industries, key=lambda x: x.get("percentage", 0), reverse=True)
    top_industries = industries[:top_n]
    others_percentage = sum(i.get("percentage", 0) for i in industries[top_n:])

    data["industries"] = top_industries
    if "others" in data:
        data["others"]["percentage"] = others_percentage
    else:
        data["others"] = {"name": "其他", "percentage": others_percentage, "color": "#B4C7E7"}

    data["total"] = sum(i.get("percentage", 0) for i in top_industries) + others_percentage
    data.setdefault("user_id", user_id)
    return data


def create_share(
    user_id: str,
    share_type: str,
    content_scope: str,
    custom_text: Optional[str] = None
) -> Dict[str, Any]:
    """
    生成风险诊断分享内容。

    Args:
        user_id: 用户标识
        share_type: poster / link / wechat
        content_scope: summary / full
        custom_text: 用户自定义文案（可选）

    Returns:
        分享 ID、链接、海报地址、过期时间等
    """
    share_id = f"sh_{uuid.uuid4().hex[:8]}"
    expire_at = (datetime.utcnow() + timedelta(hours=8, days=7)).strftime("%Y-%m-%d %H:%M:%S")

    title = "我的账户健康度 72 分，快来看看你的！"
    desc = "良好（亚健康）- 收益稳健，但行业集中度偏高"
    if custom_text:
        desc = custom_text

    return {
        "share_id": share_id,
        "share_url": f"https://app.example.com/risk-report?token={share_id}",
        "poster_url": f"https://cdn.example.com/posters/risk_{share_id}.png",
        "expire_at": expire_at,
        "title": title,
        "desc": desc,
        "share_type": share_type,
        "content_scope": content_scope,
        "user_id": user_id,
        "disclaimer": "以上分享内容基于模拟数据生成，仅供参考，不构成投资建议。"
    }


def get_ai_solution(user_id: str, scenario: str = "risk_optimization") -> Dict[str, Any]:
    """
    获取 AI 优化方案摘要。

    Args:
        user_id: 用户标识
        scenario: risk_optimization / rebalance / goal_based

    Returns:
        AI 优化建议摘要
    """
    data = _load_mock_json("ai_solution.json")
    data["scenario"] = scenario
    data.setdefault("user_id", user_id)
    return data


def get_overview(user_id: str) -> Dict[str, Any]:
    """
    聚合接口：一次性返回 report / dimensions / risk_alerts / industry_dist。

    Args:
        user_id: 用户标识

    Returns:
        风险诊断聚合数据
    """
    return {
        "report": get_risk_report(user_id),
        "dimensions": get_dimensions(user_id),
        "risk_alerts": get_risk_alerts(user_id),
        "industry_dist": get_industry_distribution(user_id),
        "meta": {
            "data_time": datetime.utcnow().strftime("%Y-%m-%d"),
            "is_cache": True
        }
    }
