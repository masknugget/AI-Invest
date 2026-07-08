import logging
from typing import Any, Dict, Optional

from app.core.db.connection import _init_db

# 简单日志：模块名作为 logger 名，便于追踪
logger = logging.getLogger(__name__)


def find_qa_pair(uuid_str: str) -> Optional[Dict[str, Any]]:
    """
    根据 UUID 从 MongoDB `qa_pair` 集合查询单条问答记录。

    Args:
        uuid_str: 问答记录的唯一标识 UUID。

    Returns:
        Optional[Dict]: 问答记录字典；找不到或发生异常时返回 None。
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
