import logging
from typing import Any, Dict, Optional

from app.core.db.connection import _init_db

# 简单日志：模块名作为 logger 名，便于追踪
logger = logging.getLogger(__name__)


def get_insight_by_id(insight_id: str) -> Optional[Dict[str, Any]]:
    """
    根据 ID 从 MongoDB `insight_agg` 集合查询单条洞察数据。

    Args:
        insight_id: Insight ID（MongoDB _id 的字符串形式，或 article_id 字符串）。

    Returns:
        Optional[Dict]: 洞察数据字典；找不到或发生异常时返回 None。
    """
    from bson import ObjectId

    # client 由 _init_db 作为单例管理，此处仅取出 db 使用
    _, db = _init_db()
    try:
        coll = db["insight_agg"]

        # 优先尝试将 insight_id 作为 ObjectId 查询 _id 字段
        try:
            obj_id = ObjectId(insight_id)
        except Exception:
            # 不是有效的 ObjectId，则回退到 article_id 字符串匹配
            logger.warning("insight_id 不是有效 ObjectId，尝试匹配 article_id: %s", insight_id)
            doc = coll.find_one({"article_id": insight_id})
            if doc:
                doc.pop("_id", None)
                logger.info("get_insight_by_id: article_id=%s found", insight_id)
                return doc
            logger.info("get_insight_by_id: article_id=%s not found", insight_id)
            return None

        doc = coll.find_one({"_id": obj_id})
        if doc:
            doc.pop("_id", None)
            logger.info("get_insight_by_id: _id=%s found", insight_id)
            return doc

        logger.info("get_insight_by_id: _id=%s not found", insight_id)
        return None
    except Exception as e:
        logger.exception("查询 Insight 失败: insight_id=%s, error=%s", insight_id, e)
        return None
