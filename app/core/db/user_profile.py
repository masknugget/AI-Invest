import logging
from datetime import datetime
from typing import Any, Dict, Optional, Union

from pymongo import DESCENDING

from app.core.db.connection import _init_db

# 简单日志：模块名作为 logger 名，便于追踪
logger = logging.getLogger(__name__)


def save_user_profile(
    user_id: Union[str, int],
    profile_data: Dict[str, Any],
) -> Optional[str]:
    """
    保存用户画像到 MongoDB `user_profiles` 集合。

    Args:
        user_id: 用户ID。
        profile_data: LLM 生成的画像数据，通常包含 generatedTags、summary、audit 等字段。

    Returns:
        Optional[str]: 插入文档的 _id 字符串；失败返回 None。
    """
    # client 由 _init_db 作为单例管理，此处仅取出 db 使用
    _, db = _init_db()
    try:
        coll = db["user_profiles"]

        now = datetime.now()
        doc = {
            "user_id": user_id,
            "generatedTags": profile_data.get("generatedTags", []),
            "summary": profile_data.get("summary", {}),
            "audit": profile_data.get("audit", {}),
            "datetime": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "timestamp": now,
        }

        result = coll.insert_one(doc)
        inserted_id = str(result.inserted_id)
        logger.info("user_profile saved: user_id=%s inserted_id=%s", user_id, inserted_id)
        return inserted_id
    except Exception as e:
        logger.exception("保存用户画像失败: user_id=%s, error=%s", user_id, e)
        return None


def get_user_profile(user_id: Union[str, int]) -> Optional[Dict[str, Any]]:
    """
    获取用户最新画像。

    从 MongoDB `user_profiles` 集合中，根据 user_id 获取最新的一条记录（按 datetime 降序）。

    Args:
        user_id: 用户ID。

    Returns:
        Optional[Dict]: 用户画像数据；找不到或发生异常返回 None。
    """
    _, db = _init_db()
    try:
        coll = db["user_profiles"]

        doc = coll.find_one(
            {"user_id": user_id},
            sort=[("datetime", DESCENDING)],
        )

        if doc:
            doc.pop("_id", None)
            logger.info("get_user_profile: user_id=%s found", user_id)
            return doc

        logger.info("get_user_profile: user_id=%s not found", user_id)
        return None
    except Exception as e:
        logger.exception("查询用户画像失败: user_id=%s, error=%s", user_id, e)
        return None
