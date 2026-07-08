import logging
from datetime import datetime
from typing import Any, Dict, List, Union

from pymongo import ASCENDING

from app.core.db.connection import _init_db

# 简单日志：模块名作为 logger 名，便于追踪
logger = logging.getLogger(__name__)


def log_chat_history(data: Dict[str, Any]) -> None:
    """
    保存 ChatTracker 的 to_dict() 数据到 MongoDB。

    Args:
        data: ChatTracker.to_dict() 返回的字典，包含用户对话历史。
              关键字段包括 user_id、chat_id、conversation_id、messages 等。
    """
    # client 由 _init_db 作为单例管理，此处仅取出 db 使用
    _, db = _init_db()
    try:
        coll = db["chat_history"]
        log_entry = {
            "timestamp": datetime.now(),
            "user_id": data.get("user_id"),
            "chat_id": data.get("chat_id"),
            "conversation_id": data.get("conversation_id"),
            "messages": data.get("messages", []),
            "user_query": data.get("user_query", ""),
            "content": data.get("content", ""),
            "create_datetime": data.get("create_datetime"),
            "title": data.get("title"),
            "intent": data.get("intent", ""),
            "plot_line": data.get("plot_line", {}),
            "ref_new_list": data.get("ref_new_list", []),
            "ref_fin_report": data.get("ref_fin_report", []),
        }
        coll.insert_one(log_entry)
        logger.info("chat_history saved: user_id=%s conversation_id=%s", data.get("user_id"), data.get("conversation_id"))
    except Exception as e:
        logger.exception("保存对话日志失败: %s", e)


def get_chat_history(
    user_id: Union[str, int],
    conversation_id: Union[str, None] = None,
) -> List[Dict[str, Any]]:
    """
    通过 user_id 和 conversation_id 查找 chat_history。

    Args:
        user_id: 用户ID。
        conversation_id: 对话ID。为 None 时返回该用户的全部聊天记录。

    Returns:
        List[Dict]: 聊天记录列表，按 create_datetime 升序排列，不含 MongoDB _id 字段。
    """
    if user_id is None:
        return []

    _, db = _init_db()
    try:
        coll = db["chat_history"]
        filter_dict = {"user_id": user_id}
        if conversation_id is not None:
            filter_dict["conversation_id"] = conversation_id

        cursor = coll.find(filter_dict).sort("create_datetime", ASCENDING)
        records = [{k: v for k, v in doc.items() if k != "_id"} for doc in cursor]

        logger.info(
            "get_chat_history: user_id=%s conversation_id=%s count=%d",
            user_id,
            conversation_id,
            len(records),
        )
        return records
    except Exception as e:
        logger.exception("查询对话历史失败: user_id=%s conversation_id=%s, error=%s", user_id, conversation_id, e)
        return []


def del_user_conversation(
    user_id: Union[str, int],
    conversation_id: str,
) -> bool:
    """
    删除指定用户和会话ID的所有聊天记录。

    Args:
        user_id: 用户ID。
        conversation_id: 会话ID。

    Returns:
        bool: 删除成功且至少删除一条记录返回 True，否则返回 False。
    """
    if not user_id or not conversation_id:
        return False

    _, db = _init_db()
    try:
        coll = db["chat_history"]
        filter_dict = {
            "user_id": user_id,
            "conversation_id": conversation_id,
        }

        result = coll.delete_many(filter_dict)
        deleted = result.deleted_count
        logger.info(
            "del_user_conversation: user_id=%s conversation_id=%s deleted=%d",
            user_id,
            conversation_id,
            deleted,
        )
        return deleted > 0
    except Exception as e:
        logger.exception("删除对话失败: user_id=%s conversation_id=%s, error=%s", user_id, conversation_id, e)
        return False


def update_conversation_title(
    user_id: Union[str, int],
    conversation_id: str,
    title: str,
) -> bool:
    """
    更新指定会话的标题。

    Args:
        user_id: 用户ID。
        conversation_id: 会话ID。
        title: 新的会话标题。

    Returns:
        bool: 更新成功返回 True，否则返回 False。
    """
    if not user_id or not conversation_id:
        return False

    _, db = _init_db()
    try:
        coll = db["chat_history"]
        filter_dict = {
            "user_id": user_id,
            "conversation_id": conversation_id,
        }

        result = coll.find_one_and_update(
            filter_dict,
            {"$set": {"title": title}},
            sort=[("create_datetime", ASCENDING)],
            return_document=True,
        )

        updated = result is not None
        logger.info(
            "update_conversation_title: user_id=%s conversation_id=%s title=%s updated=%s",
            user_id,
            conversation_id,
            title,
            updated,
        )
        return updated
    except Exception as e:
        logger.exception(
            "更新会话标题失败: user_id=%s conversation_id=%s title=%s, error=%s",
            user_id,
            conversation_id,
            title,
            e,
        )
        return False
