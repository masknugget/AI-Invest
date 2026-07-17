import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pymongo import ASCENDING, DESCENDING

from app.core.db.connection import _init_db

# 简单日志：模块名作为 logger 名，便于追踪
logger = logging.getLogger(__name__)


def find_qa_pair(uuid_str: str) -> Optional[Dict[str, Any]]:
    """
    根据 UUID 从 MongoDB `qa_pair` 集合查询单条问答记录。

    Args:
        uuid_str: 问答记录的唯一标识 UUID。

    Returns:
        Optional[Dict]: 问答记录字典；找不到或发生异常返回 None。
    """
    # client 由 _init_db 作为单例管理，此处仅取出 db 使用
    _, db = _init_db()
    try:
        coll = db["qa_pair"]
        doc = coll.find_one({"uuid": uuid_str})

        if doc:
            logger.info("find_qa_pair: uuid=%s found", uuid_str)
        else:
            logger.info("find_qa_pair: uuid=%s not found", uuid_str)
        return doc
    except Exception as e:
        logger.exception("查询问答记录失败: uuid=%s, error=%s", uuid_str, e)
        return None


def get_industry_by_code(symbol_code: str) -> Optional[Dict[str, Any]]:
    """
    根据股票代码查询行业、板块与市值分组信息。

    Args:
        symbol_code: 股票代码。

    Returns:
        Optional[Dict]: 包含 industry_name、sector_name、market_cap_group_name 的字典；
                        找不到或发生异常返回 None。
    """
    _, db = _init_db()
    try:
        coll = db["market_fundamental_analysis_v1"]
        doc = coll.find_one({"symbol": symbol_code})

        if doc:
            doc.pop("_id", None)
            logger.info("get_industry_by_code: symbol_code=%s found", symbol_code)
            return {
                "industry_name": doc.get("industry_name", ""),
                "sector_name": doc.get("sector_name", ""),
                "market_cap_group_name": doc.get("market_cap_group_name", ""),
            }

        logger.info("get_industry_by_code: symbol_code=%s not found", symbol_code)
        return None
    except Exception as e:
        logger.exception("查询行业信息失败: symbol_code=%s, error=%s", symbol_code, e)
        return None


def save_dimensions(
    formatted: Dict[str, Any],
    user_id: Union[str, int] = "admin123",
) -> None:
    """
    保存 format_dimensions(result) 返回的维度评分结果到 MongoDB。

    Args:
        formatted: format_dimensions 返回的字典，包含 dimensions、benchmark、disclaimer。
        user_id: 用户ID，默认 admin123。
    """
    _, db = _init_db()
    try:
        coll = db["p_advisor_dimensions"]
        log_entry = {
            "timestamp": datetime.now(),
            "user_id": user_id,
            "dimensions": formatted.get("dimensions", []),
            "benchmark": formatted.get("benchmark", []),
            "disclaimer": formatted.get("disclaimer", ""),
        }
        coll.insert_one(log_entry)
        logger.info("p_advisor_dimensions saved: user_id=%s", user_id)
    except Exception as e:
        logger.exception("保存维度评分失败: user_id=%s, error=%s", user_id, e)


def get_dimensions(
    user_id: Union[str, int] = "admin123",
) -> List[Dict[str, Any]]:
    """
    通过 user_id 查找保存的维度评分结果。

    Args:
        user_id: 用户ID，默认 admin123。

    Returns:
        List[Dict]: 维度评分记录列表，按 timestamp 升序排列，不含 MongoDB _id 字段。
    """
    if user_id is None:
        return []

    _, db = _init_db()
    try:
        coll = db["p_advisor_dimensions"]
        cursor = coll.find({"user_id": user_id}).sort("timestamp", ASCENDING)
        records = [{k: v for k, v in doc.items() if k != "_id"} for doc in cursor]

        logger.info(
            "get_dimensions: user_id=%s count=%d",
            user_id,
            len(records),
        )
        return records
    except Exception as e:
        logger.exception("查询维度评分失败: user_id=%s, error=%s", user_id, e)
        return []


def get_latest_dimensions(
    user_id: Union[str, int] = "admin123",
) -> Dict[str, Any]:
    """
    查询用户最新的维度评分结果。

    Args:
        user_id: 用户ID，默认 admin123。

    Returns:
        Dict: 最新的维度评分记录；找不到或发生异常返回空字典。
    """
    if user_id is None:
        return {}

    _, db = _init_db()
    try:
        coll = db["p_advisor_dimensions"]
        doc = coll.find_one(
            {"user_id": user_id},
            sort=[("timestamp", DESCENDING)],
        )

        if doc:
            doc.pop("_id", None)
            logger.info("get_latest_dimensions: user_id=%s found", user_id)
            return doc

        logger.info("get_latest_dimensions: user_id=%s not found", user_id)
        return {}
    except Exception as e:
        logger.exception("查询最新维度评分失败: user_id=%s, error=%s", user_id, e)
        return {}


def save_industry_distribution(
    distribution: Dict[str, Any],
    user_id: Union[str, int] = "admin123",
) -> None:
    """
    保存用户行业分布数据到 MongoDB。

    Args:
        distribution: 行业分布字典，例如 {"Specialty Retailers": 0.7, "Natural Gas Utilities": 0.3}。
        user_id: 用户ID，默认 admin123。
    """
    _, db = _init_db()
    try:
        coll = db["user_industry_distribution"]
        log_entry = {
            "date_time": datetime.now(),
            "user_id": user_id,
            "distribution": distribution,
        }
        coll.insert_one(log_entry)
        logger.info("user_industry_distribution saved: user_id=%s", user_id)
    except Exception as e:
        logger.exception("保存行业分布失败: user_id=%s, error=%s", user_id, e)


def get_industry_distribution(
    user_id: Union[str, int] = "admin123",
    top_n: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """
    查询用户最新的行业分布数据。

    Args:
        user_id: 用户ID，默认 admin123。
        top_n: 返回前 N 个行业，其余归入"其他"；为 None 时返回原始分布记录。

    Returns:
        Optional[Dict]: 最新的行业分布记录；找不到或发生异常返回 None。
    """
    if user_id is None:
        return None

    _, db = _init_db()
    try:
        coll = db["user_industry_distribution"]
        doc = coll.find_one(
            {"user_id": user_id},
            sort=[("date_time", DESCENDING)],
        )

        if doc:
            doc.pop("_id", None)

            distribution: Dict[str, Any] = doc.get("distribution", {})
            if top_n is not None and distribution:
                sorted_items = sorted(
                    distribution.items(), key=lambda x: x[1], reverse=True
                )
                top_items = sorted_items[:top_n]
                others_value = sum(v for _, v in sorted_items[top_n:])
                industries = [
                    {"name": name, "percentage": round(value, 4)}
                    for name, value in top_items
                ]
                doc["industries"] = industries
                doc["others"] = {
                    "name": "其他",
                    "percentage": round(others_value, 4),
                    "color": "#B4C7E7",
                }
                doc["total"] = round(sum(i["percentage"] for i in industries) + doc["others"]["percentage"], 4)

            logger.info("get_industry_distribution: user_id=%s found", user_id)
            return doc

        logger.info("get_industry_distribution: user_id=%s not found", user_id)
        return None
    except Exception as e:
        logger.exception("查询行业分布失败: user_id=%s, error=%s", user_id, e)
        return None


def save_risk_alert(
    formatted: Dict[str, Any],
    user_id: Union[str, int] = "admin123",
) -> None:
    """
    保存 format_risk_alerts(risks) 返回的风险提示结果到 MongoDB。

    Args:
        formatted: format_risk_alerts 返回的字典，包含 total_count、alerts、disclaimer。
        user_id: 用户ID，默认 admin123。
    """
    _, db = _init_db()
    try:
        coll = db["p_advisor_risk_alerts"]
        log_entry = {
            "timestamp": datetime.now(),
            "user_id": user_id,
            "total_count": formatted.get("total_count", 0),
            "alerts": formatted.get("alerts", []),
            "disclaimer": formatted.get("disclaimer", ""),
        }
        coll.insert_one(log_entry)
        logger.info("p_advisor_risk_alerts saved: user_id=%s", user_id)
    except Exception as e:
        logger.exception("保存风险提示失败: user_id=%s, error=%s", user_id, e)


def get_risk_alert(
    user_id: Union[str, int] = "admin123",
    severity: Optional[str] = "all",
) -> Optional[Dict[str, Any]]:
    """
    查询用户最新的风险提示数据，支持按严重程度过滤。

    Args:
        user_id: 用户ID，默认 admin123。
        severity: 风险等级过滤 all/high/medium/low。

    Returns:
        Optional[Dict]: 最新的风险提示记录，不含 MongoDB _id 字段；
                        找不到或发生异常返回 None。
    """
    if user_id is None:
        return None

    _, db = _init_db()
    try:
        coll = db["p_advisor_risk_alerts"]
        doc = coll.find_one(
            {"user_id": user_id},
            sort=[("timestamp", DESCENDING)],
        )

        if doc:
            doc.pop("_id", None)
            alerts: List[Dict[str, Any]] = doc.get("alerts", [])
            if severity and severity.lower() != "all":
                alerts = [
                    a for a in alerts if a.get("severity", "").lower() == severity.lower()
                ]
            doc["alerts"] = alerts
            doc["total_count"] = len(alerts)
            logger.info("get_risk_alert: user_id=%s found", user_id)
            return doc

        logger.info("get_risk_alert: user_id=%s not found", user_id)
        return None
    except Exception as e:
        logger.exception("查询风险提示失败: user_id=%s, error=%s", user_id, e)
        return None


def save_risk_report(
    formatted: Dict[str, Any],
    user_id: Union[str, int] = "admin123",
) -> None:
    """
    保存 format_report(result, comprehensive_str) 返回的综合报告到 MongoDB。

    Args:
        formatted: format_report 返回的字典，包含 health_score、rating、comment、update_time、disclaimer。
        user_id: 用户ID，默认 admin123。
    """
    _, db = _init_db()
    try:
        coll = db["p_advisor_risk_report"]
        log_entry = {
            "timestamp": datetime.now(),
            "user_id": user_id,
            "health_score": formatted.get("health_score"),
            "rating": formatted.get("rating", {}),
            "comment": formatted.get("comment", ""),
            "update_time": formatted.get("update_time", ""),
            "disclaimer": formatted.get("disclaimer", ""),
        }
        coll.insert_one(log_entry)
        logger.info("p_advisor_risk_report saved: user_id=%s", user_id)
    except Exception as e:
        logger.exception("保存综合报告失败: user_id=%s, error=%s", user_id, e)


def get_risk_report(
    user_id: Union[str, int] = "admin123",
    account_type: Optional[str] = None,
    diagnosis_date: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    查询用户最新的综合报告数据。

    Args:
        user_id: 用户ID，默认 admin123。
        account_type: 账户类型，可选 fund/stock/all，仅覆盖返回字段。
        diagnosis_date: 诊断日期，可选，仅覆盖返回字段。

    Returns:
        Optional[Dict]: 最新的综合报告记录，不含 MongoDB _id 字段；
                        找不到或发生异常返回 None。
    """
    if user_id is None:
        return None

    _, db = _init_db()
    try:
        coll = db["p_advisor_risk_report"]
        doc = coll.find_one(
            {"user_id": user_id},
            sort=[("timestamp", DESCENDING)],
        )

        if doc:
            doc.pop("_id", None)
            if account_type is not None:
                doc["account_type"] = account_type
            if diagnosis_date is not None:
                doc["diagnosis_date"] = diagnosis_date
            logger.info("get_risk_report: user_id=%s found", user_id)
            return doc

        logger.info("get_risk_report: user_id=%s not found", user_id)
        return None
    except Exception as e:
        logger.exception("查询综合报告失败: user_id=%s, error=%s", user_id, e)
        return None


def save_advisor_result(
    formatted: Dict[str, Any],
    user_id: Union[str, int] = "admin123",
) -> None:
    """
    保存整合后的 portfolio advisor 结果到 MongoDB。

    Args:
        formatted: format_advisor_result 返回的字典，包含 dimensions、risk_report、risk_alert、industry_distribution。
        user_id: 用户ID，默认 admin123。
    """
    _, db = _init_db()
    try:
        coll = db["p_advisor_result"]
        log_entry = {
            "timestamp": datetime.now(),
            "user_id": user_id,
            "dimensions": formatted.get("dimensions", {}),
            "risk_report": formatted.get("risk_report", {}),
            "risk_alert": formatted.get("risk_alert", {}),
            "industry_distribution": formatted.get("industry_distribution", {}),
            "stress_test": formatted.get("stress_test", {}),
        }
        coll.insert_one(log_entry)
        logger.info("p_advisor_result saved: user_id=%s", user_id)
    except Exception as e:
        logger.exception("保存 advisor 结果失败: user_id=%s, error=%s", user_id, e)


def get_advisor_result(
    user_id: Union[str, int] = "admin123",
) -> Optional[Dict[str, Any]]:
    """
    查询用户最新的整合 advisor 结果。

    Args:
        user_id: 用户ID，默认 admin123。

    Returns:
        Optional[Dict]: 最新的整合 advisor 结果记录，不含 MongoDB _id 字段；
                        找不到或发生异常返回 None。
    """
    if user_id is None:
        return None

    _, db = _init_db()
    try:
        coll = db["p_advisor_result"]
        doc = coll.find_one(
            {"user_id": user_id},
            sort=[("timestamp", DESCENDING)],
        )

        if doc:
            doc.pop("_id", None)
            logger.info("get_advisor_result: user_id=%s found", user_id)
            return doc

        logger.info("get_advisor_result: user_id=%s not found", user_id)
        return None
    except Exception as e:
        logger.exception("查询 advisor 结果失败: user_id=%s, error=%s", user_id, e)
        return None


def get_ai_solution(
    user_id: Union[str, int] = "admin123",
    scenario: str = "risk_optimization",
) -> Dict[str, Any]:
    """
    获取用户最新的 AI 优化方案摘要。

    当前优先从整合 advisor 结果中提取；若无记录则返回仅包含 scenario 的占位数据。

    Args:
        user_id: 用户ID，默认 admin123。
        scenario: 场景，如 risk_optimization / rebalance / goal_based。

    Returns:
        Dict: AI 优化方案摘要。
    """
    result = get_advisor_result(user_id) or {}
    data = result.get("risk_report", {}) if result else {}
    data = dict(data)
    data.setdefault("scenario", scenario)
    data.setdefault("user_id", user_id)
    return data


def get_overview(
    user_id: Union[str, int] = "admin123",
) -> Dict[str, Any]:
    """
    聚合返回风险诊断数据：report / dimensions / risk_alerts / industry_dist。

    Args:
        user_id: 用户ID，默认 admin123。

    Returns:
        Dict: 聚合数据。
    """
    now = datetime.now()

    data = get_risk_report(user_id)
    alerts = data.get("risk_alert").get("alerts")
    data_dimensions = get_latest_dimensions(user_id)

    dist = get_industry_distribution(user_id) or {}
    dist = dist.get("distribution", {})
    dist_list = list(dist.values())

    return {
        "report": data.get('risk_report',{}),
        "dimensions": data_dimensions.get("dimensions", {}),
        "risk_alerts": alerts,
        "industry_dist": dist_list,
        "meta": {
            "data_time": now.strftime("%Y-%m-%d"),
            "is_cache": True,
        },
    }


def save_rebalance_plans(
    formatted_plans: List[Dict[str, Any]],
    user_id: Union[str, int] = "admin123",
) -> None:
    """
    保存格式化后的调仓方案列表到 MongoDB。

    Args:
        formatted_plans: format_rebalance_plans 返回的 dict 列表。
        user_id: 用户ID，默认 admin123。
    """
    _, db = _init_db()
    try:
        coll = db["p_advisor_rebalance_plans"]
        log_entry = {
            "date_time": datetime.now(),
            "user_id": user_id,
            "plans": formatted_plans,
        }
        coll.insert_one(log_entry)
        logger.info("p_advisor_rebalance_plans saved: user_id=%s", user_id)
    except Exception as e:
        logger.exception("保存调仓方案失败: user_id=%s, error=%s", user_id, e)


def get_rebalance_plans(
    user_id: Union[str, int] = "admin123",
) -> Optional[List[Dict[str, Any]]]:
    """
    查询用户最新的调仓方案列表。

    Args:
        user_id: 用户ID，默认 admin123。

    Returns:
        Optional[List[Dict]]: 最新的调仓方案列表；找不到或发生异常返回 None。
    """
    if user_id is None:
        return None

    _, db = _init_db()
    try:
        coll = db["p_advisor_rebalance_plans"]
        doc = coll.find_one(
            {"user_id": user_id},
            sort=[("date_time", DESCENDING)],
        )

        if doc:
            doc.pop("_id", None)
            logger.info("get_rebalance_plans: user_id=%s found", user_id)
            return doc.get("plans", [])

        logger.info("get_rebalance_plans: user_id=%s not found", user_id)
        return None
    except Exception as e:
        logger.exception("查询调仓方案失败: user_id=%s, error=%s", user_id, e)
        return None


def save_stress_report(
    full_report: Dict[str, Any],
    user_id: Union[str, int] = "admin123",
) -> None:
    """
    保存格式化后的压力测试综合报告到 MongoDB。

    Args:
        full_report: format_all_stress_reports 返回的字典。
        user_id: 用户ID，默认 admin123。
    """
    _, db = _init_db()
    try:
        coll = db["p_advisor_stress_report"]
        log_entry = {
            "date_time": datetime.now(),
            "user_id": user_id,
            "report": full_report,
        }
        coll.insert_one(log_entry)
        logger.info("p_advisor_stress_report saved: user_id=%s", user_id)
    except Exception as e:
        logger.exception("保存压力测试报告失败: user_id=%s, error=%s", user_id, e)


def get_stress_report(
    user_id: Union[str, int] = "admin123",
) -> Optional[Dict[str, Any]]:
    """
    查询用户最新的压力测试综合报告。

    Args:
        user_id: 用户ID，默认 admin123。

    Returns:
        Optional[Dict]: 最新的压力测试报告；找不到或发生异常返回 None。
    """
    if user_id is None:
        return None

    _, db = _init_db()
    try:
        coll = db["p_advisor_stress_report"]
        doc = coll.find_one(
            {"user_id": user_id},
            sort=[("date_time", DESCENDING)],
        )

        if doc:
            doc.pop("_id", None)
            logger.info("get_stress_report: user_id=%s found", user_id)
            return doc.get("report", {})

        logger.info("get_stress_report: user_id=%s not found", user_id)
        return None
    except Exception as e:
        logger.exception("查询压力测试报告失败: user_id=%s, error=%s", user_id, e)
        return None


def save_faq(
    faq_list: List[Dict[str, Any]],
    user_id: Union[str, int] = "admin123",
) -> None:
    """
    保存 FAQ 列表到 MongoDB。

    Args:
        faq_list: FAQ 条目列表，每个条目包含 q 与 anwser 字段。
        user_id: 用户ID，默认 admin123。
    """
    _, db = _init_db()
    try:
        coll = db["p_advisor_faq"]
        log_entry = {
            "timestamp": datetime.now(),
            "user_id": user_id,
            "faq": faq_list,
        }
        coll.insert_one(log_entry)
        logger.info("p_advisor_faq saved: user_id=%s count=%d", user_id, len(faq_list))
    except Exception as e:
        logger.exception("保存 FAQ 失败: user_id=%s, error=%s", user_id, e)


def get_faq(
    user_id: Union[str, int] = "admin123",
) -> List[Dict[str, Any]]:
    """
    查询用户最新的 FAQ 列表。

    Args:
        user_id: 用户ID，默认 admin123。

    Returns:
        List[Dict]: FAQ 条目列表；找不到或发生异常返回空列表。
    """
    if user_id is None:
        return []

    _, db = _init_db()
    try:
        coll = db["p_advisor_faq"]
        doc = coll.find_one(
            {"user_id": user_id},
            sort=[("timestamp", DESCENDING)],
        )

        if doc:
            logger.info("get_faq: user_id=%s found", user_id)
            return doc.get("faq", [])

        logger.info("get_faq: user_id=%s not found", user_id)
        return []
    except Exception as e:
        logger.exception("查询 FAQ 失败: user_id=%s, error=%s", user_id, e)
        return []
