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
