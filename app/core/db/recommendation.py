import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import pandas as pd
from pymongo import DESCENDING

from app.core.db.connection import _init_db

# 简单日志：模块名作为 logger 名，便于追踪
logger = logging.getLogger(__name__)


def log_rec_history(data: Dict[str, Any]) -> None:
    """
    保存推荐历史记录到 MongoDB `rec_history` 集合。

    Args:
        data: 推荐记录字典，包含 user_id、rec_content_ids、create_datetime 等字段。
    """
    # client 由 _init_db 作为单例管理，此处仅取出 db 使用
    _, db = _init_db()
    try:
        coll = db["rec_history"]
        log_entry = {
            "timestamp": datetime.now(),
            "user_id": data.get("user_id"),
            "rec_content_ids": data.get("rec_content_ids"),
            "create_datetime": data.get("create_datetime"),
        }
        coll.insert_one(log_entry)
        logger.info(
            "rec_history saved: user_id=%s rec_count=%s",
            data.get("user_id"),
            len(data.get("rec_content_ids", [])),
        )
    except Exception as e:
        logger.exception("保存推荐日志失败: %s", e)


def get_rec_history(
    user_id: Union[str, int],
    conversation_id: Optional[str] = None,
) -> List[str]:
    """
    查询用户最近推荐过的内容 ID 列表。

    Args:
        user_id: 用户ID。
        conversation_id: 对话ID。为 None 时查询该用户的全部推荐历史。

    Returns:
        List[str]: 去重后的推荐内容 ID 列表，最多 30 条。
    """
    if user_id is None:
        return []

    _, db = _init_db()
    try:
        coll = db["rec_history"]
        filter_dict = {"user_id": user_id}
        if conversation_id is not None:
            filter_dict["conversation_id"] = conversation_id

        # 按创建时间降序，取最近 30 条记录进行 ID 去重
        cursor = coll.find(filter_dict).sort("create_datetime", DESCENDING).limit(30)
        records = [{k: v for k, v in doc.items() if k != "_id"} for doc in cursor]

        rec_history: set = set()
        for record in records:
            ids = record.get("rec_content_ids", [])
            if isinstance(ids, list):
                rec_history.update(ids)

        result = list(rec_history)[:30]
        logger.info(
            "get_rec_history: user_id=%s conversation_id=%s unique_ids=%d",
            user_id,
            conversation_id,
            len(result),
        )
        return result
    except Exception as e:
        logger.exception(
            "查询推荐历史失败: user_id=%s conversation_id=%s, error=%s",
            user_id,
            conversation_id,
            e,
        )
        return []


def log_rec_content_history(
    user_id: Union[str, int],
    rec_content_data: List[Dict[str, Any]],
) -> None:
    """
    保存推荐内容的完整数据到 MongoDB `rec_content_history` 集合。

    Args:
        user_id: 用户ID。
        rec_content_data: 推荐内容数据列表，每条包含一条推荐的完整信息。
    """
    _, db = _init_db()
    try:
        coll = db["rec_content_history"]
        log_entry = {
            "timestamp": datetime.now(),
            "user_id": user_id,
            "rec_content_data": rec_content_data,
            "create_datetime": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        coll.insert_one(log_entry)
        logger.info(
            "rec_content_history saved: user_id=%s count=%d",
            user_id,
            len(rec_content_data),
        )
    except Exception as e:
        logger.exception("保存推荐内容日志失败: user_id=%s, error=%s", user_id, e)


def log_views_insight(
    user_id: Union[str, int],
    insight_id: str,
) -> None:
    """
    保存 Insight 浏览记录到 MongoDB `insight_views` 集合。

    Args:
        user_id: 用户ID。
        insight_id: 浏览的 Insight ID。
    """
    _, db = _init_db()
    try:
        coll = db["insight_views"]
        log_entry = {
            "timestamp": datetime.now(),
            "user_id": user_id,
            "insight_id": insight_id,
            "create_datetime": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        coll.insert_one(log_entry)
        logger.info("insight_views saved: user_id=%s insight_id=%s", user_id, insight_id)
    except Exception as e:
        logger.exception(
            "保存浏览记录失败: user_id=%s insight_id=%s, error=%s",
            user_id,
            insight_id,
            e,
        )


def get_views_insight(
    user_id: Union[str, int],
    page_size: int = 20,
    page: int = 1,
) -> Dict[str, Any]:
    """
    查询用户 Insight 浏览历史。

    Args:
        user_id: 用户ID。
        page_size: 每页数量。
        page: 页码，从 1 开始。

    Returns:
        Dict: 包含 items 列表和 pagination 分页信息的字典。
    """
    empty_result = {
        "items": [],
        "pagination": {
            "page": page,
            "pageSize": page_size,
            "total": 0,
            "hasMore": False,
        },
    }

    if user_id is None:
        return empty_result

    _, db = _init_db()
    try:
        coll = db["insight_views"]
        filter_dict = {"user_id": user_id}

        # 分页查询：按时间倒序
        skip = (page - 1) * page_size
        cursor = coll.find(filter_dict).sort("timestamp", DESCENDING).skip(skip).limit(page_size)
        items = [{k: v for k, v in doc.items() if k != "_id"} for doc in cursor]

        # 对 insight_id 去重，保留时间最近的一条
        if items:
            df = pd.DataFrame(items)
            unique_df = df.drop_duplicates(subset="insight_id", keep="first")
            items = unique_df.to_dict("records")

        total = coll.count_documents(filter_dict)
        logger.info(
            "get_views_insight: user_id=%s page=%d page_size=%d total=%d",
            user_id,
            page,
            page_size,
            total,
        )
        return {
            "items": items,
            "pagination": {
                "page": page,
                "pageSize": page_size,
                "total": total,
                "hasMore": total > skip + len(items),
            },
        }
    except Exception as e:
        logger.exception("查询浏览历史失败: user_id=%s, error=%s", user_id, e)
        return empty_result


def delete_views_insight(
    user_id: Union[str, int],
    insight_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    删除用户 Insight 浏览历史。

    Args:
        user_id: 用户ID。
        insight_id: 可选的 Insight ID。为 None 时清空该用户的全部浏览历史；
            否则仅删除该 Insight 的浏览记录。

    Returns:
        Dict: 包含 success 状态和删除数量的字典。
    """
    result = {"success": False, "deleted_count": 0}
    if user_id is None:
        return result

    _, db = _init_db()
    try:
        coll = db["insight_views"]
        filter_dict = {"user_id": user_id}
        if insight_id is not None:
            filter_dict["insight_id"] = insight_id

        delete_result = coll.delete_many(filter_dict)
        result["deleted_count"] = delete_result.deleted_count
        result["success"] = True
        logger.info(
            "delete_views_insight: user_id=%s insight_id=%s deleted_count=%d",
            user_id,
            insight_id,
            result["deleted_count"],
        )
        return result
    except Exception as e:
        logger.exception(
            "删除浏览历史失败: user_id=%s insight_id=%s, error=%s",
            user_id,
            insight_id,
            e,
        )
        return result


def get_recommendation_history_docs(
    user_id: Union[str, int],
    page_size: int = 20,
    page: int = 1,
    action: Optional[str] = None,
) -> Dict[str, Any]:
    """
    查询用户推荐内容历史记录（从 `rec_content_history` 集合）。

    Args:
        user_id: 用户ID。
        page_size: 每页数量。
        page: 页码，从 1 开始。
        action: 可选过滤特定动作，如 click / dismiss / share / save。

    Returns:
        Dict: 包含 items 列表和 pagination 分页信息的字典。
    """
    empty_result = {
        "items": [],
        "pagination": {
            "page": page,
            "pageSize": page_size,
            "total": 0,
            "hasMore": False,
        },
    }

    _, db = _init_db()
    try:
        coll = db["rec_content_history"]

        # 构建查询条件
        query: Dict[str, Any] = {}
        if user_id is not None:
            query["user_id"] = user_id
        if action:
            query["action"] = action

        # 分页查询：按时间倒序
        skip = (page - 1) * page_size
        cursor = coll.find(query).sort("timestamp", DESCENDING).skip(skip).limit(page_size)
        items = [{k: v for k, v in doc.items() if k != "_id"} for doc in cursor]

        total = coll.count_documents(query)
        logger.info(
            "get_recommendation_history_docs: user_id=%s action=%s page=%d page_size=%d total=%d",
            user_id,
            action,
            page,
            page_size,
            total,
        )
        return {
            "items": items,
            "pagination": {
                "page": page,
                "pageSize": page_size,
                "total": total,
                "hasMore": total > skip + len(items),
            },
        }
    except Exception as e:
        logger.exception(
            "查询推荐历史失败: user_id=%s action=%s, error=%s",
            user_id,
            action,
            e,
        )
        return empty_result
