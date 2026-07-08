import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import pandas as pd
from pymongo import ASCENDING, DESCENDING
from pymongo.collection import Collection

from app.core.config import settings
from app.core.db.connection import _init_db

# 简单日志：模块名作为 logger 名，便于追踪
logger = logging.getLogger(__name__)


def _query_mongodb_news(
    symbol: str,
    start_date: str,
    end_date: str,
) -> List[Dict[str, Any]]:
    """
    按 symbol + 日期区间查询股票相关新闻。

    Args:
        symbol: 股票代码。
        start_date: 开始日期，格式 YYYY-MM-DD。
        end_date: 结束日期，格式 YYYY-MM-DD。

    Returns:
        List[Dict]: 新闻记录列表，按 trade_date 倒序。
    """
    # client 由 _init_db 作为单例管理，此处仅取出 db 使用
    _, db = _init_db()
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        collection_name = getattr(settings, "HK_SYNC_HEADLINE_COLLECTION", "hk_sync_headline")
        coll: Collection = db[collection_name]

        # 同时匹配 symbol / stock / ticker 三个字段
        filter_dict = {
            "$or": [
                {"symbol": symbol},
                {"stock": symbol},
                {"ticker": symbol},
            ],
            "trade_date": {"$gte": start_dt, "$lte": end_dt},
        }

        cursor = coll.find(filter_dict).sort("trade_date", DESCENDING)
        records = [{k: v for k, v in doc.items() if k != "_id"} for doc in cursor]
        logger.info(
            "_query_mongodb_news: symbol=%s collection=%s count=%d",
            symbol,
            collection_name,
            len(records),
        )
        return records
    except Exception as e:
        logger.exception("新闻查询错误: symbol=%s, error=%s", symbol, e)
        return []


def _query_mongodb_market_news(
    start_date: str,
    end_date: str,
    news_type: str = "global",
) -> List[Dict[str, Any]]:
    """
    按日期区间查询市场新闻。

    Args:
        start_date: 开始日期，格式 YYYY-MM-DD。
        end_date: 结束日期，格式 YYYY-MM-DD。
        news_type: 新闻类型，默认 'global'。

    Returns:
        List[Dict]: 市场新闻记录列表，按 date 倒序。
    """
    _, db = _init_db()
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        coll: Collection = db["market_news"]

        filter_dict: Dict[str, Any] = {
            "date": {"$gte": start_dt, "$lte": end_dt},
        }
        if news_type != "global":
            filter_dict["type"] = news_type

        cursor = coll.find(filter_dict).sort("date", DESCENDING)
        records = [{k: v for k, v in doc.items() if k != "_id"} for doc in cursor]
        logger.info(
            "_query_mongodb_market_news: news_type=%s count=%d",
            news_type,
            len(records),
        )
        return records
    except Exception as e:
        logger.exception("市场新闻查询错误: news_type=%s, error=%s", news_type, e)
        return []


def get_fin_report(
    symbol: str = "00001",
    state_period_start: int = 2023,
    state_period_end: int = 2025,
    market: str = "HK",
) -> tuple:
    """
    查询指定股票在财报数据库中的利润表、现金流量表和资产负债表数据。

    Args:
        symbol: 股票代码。
        state_period_start: 起始财报年度。
        state_period_end: 结束财报年度。
        market: 市场，'HK' 或 'CN'。

    Returns:
        tuple: (markdown 汇总文本, 结构化数据字典)。
    """
    _, db = _init_db()

    try:
        if market == "HK":
            col_name_inc = "hk_fin_reports_inc"
            col_name_cas = "hk_fin_reports_cas"
            col_name_bal = "hk_fin_reports_bal"
        else:
            col_name_inc = "cn_fin_reports_inc"
            col_name_cas = "cn_fin_reports_cas"
            col_name_bal = "cn_fin_reports_bal"

        col_inc = db[col_name_inc]
        col_cas = db[col_name_cas]
        col_bal = db[col_name_bal]

        filter_dict = {
            "symbol": symbol,
            "statementPeriod": {"$gte": state_period_start, "$lte": state_period_end},
        }

        # 利润表、现金流量表、资产负债表分别查询并解析
        records_inc = [{k: v for k, v in doc.items() if k != "_id"} for doc in col_inc.find(filter_dict)]
        md_inc, report_inc = parse_report(records_inc)

        records_cas = [{k: v for k, v in doc.items() if k != "_id"} for doc in col_cas.find(filter_dict)]
        md_cas, report_cas = parse_report(records_cas)

        records_bal = [{k: v for k, v in doc.items() if k != "_id"} for doc in col_bal.find(filter_dict)]
        md_bal, report_bal = parse_report(records_bal)

        md_report = str(md_bal) + "\n" + str(md_inc) + "\n" + str(md_cas)
        data_out = {
            "data_inc": report_inc,
            "data_cas": report_cas,
            "data_bal": report_bal,
        }

        logger.info(
            "get_fin_report: symbol=%s market=%s period=%d-%d",
            symbol,
            market,
            state_period_start,
            state_period_end,
        )
        return md_report, data_out
    except Exception as e:
        logger.exception("查询财报失败: symbol=%s market=%s, error=%s", symbol, market, e)
        return "", {}


def parse_report(records_filter: List[Dict[str, Any]]) -> tuple:
    """
    将财务报表记录按科目和报告期透视成 markdown 表格和结构化列表。

    Args:
        records_filter: 单张报表（inc/cas/bal）的原始记录列表。

    Returns:
        tuple: (markdown 表格字符串, 结构化列表)。
    """
    if not records_filter:
        return "", []

    data_2025 = [i for i in records_filter if i.get("statementPeriod") == 2025]
    data_2024 = [i for i in records_filter if i.get("statementPeriod") == 2024]
    data_2023 = [i for i in records_filter if i.get("statementPeriod") == 2023]

    df = pd.concat([pd.DataFrame(data_2025), pd.DataFrame(data_2024), pd.DataFrame(data_2023)])
    if df.empty:
        return "", []

    df = df[["name", "statementPeriod", "value"]]
    pivot_df = df.pivot(index="name", columns="statementPeriod", values="value")

    # 保持以 2023 年数据顺序作为索引顺序
    new_order = [i.get("name") for i in data_2023 if i.get("name")]
    if new_order:
        pivot_df = pivot_df.loc[pivot_df.index.intersection(new_order)]
    pivot_df = pivot_df.fillna(0)

    out_list = []
    for name, item in pivot_df.iterrows():
        dt = {str(k): v for k, v in item.to_dict().items()}
        tmp = {"name": name, **dt}
        out_list.append(tmp)

    md_data = pivot_df.to_markdown()
    return md_data, out_list


def parse_news(data_item: Dict[str, Any]) -> str:
    """
    将单条新闻数据格式化为 title + brief 文本。

    Args:
        data_item: 包含 headline 和 brief 的新闻字典。

    Returns:
        str: 格式化后的文本。
    """
    head_line = data_item.get("headline", "")
    brief = data_item.get("brief", "")
    return f"title: {head_line}\n{brief}\n"


def find_news(
    symbol: str = "00467",
    start_date: str = "2025-01-01",
    end_date: str = "2026-04-01",
    market: str = "HK",
) -> tuple:
    """
    查询股票新闻并返回拼接文本与原始列表。

    Args:
        symbol: 股票代码。
        start_date: 开始日期，格式 YYYY-MM-DD。
        end_date: 结束日期，格式 YYYY-MM-DD。
        market: 市场，'HK' 或 'CN'。

    Returns:
        tuple: (新闻文本, 新闻原始列表)。
    """
    if market == "HK":
        data = get_hk_news_headlines(symbol, start_date, end_date)
    else:
        data = get_cn_news_headlines(symbol, start_date, end_date)

    if not data:
        return "没有新闻数据", []

    if isinstance(data, list):
        data = data[0]

    new_list: List[Dict[str, Any]] = []
    if "raw_data" in data and isinstance(data["raw_data"], dict):
        new_list = data["raw_data"].get("newsList", [])
    elif "newList" in data:
        new_list = data["newList"]

    content_news = "\n".join([parse_news(i) for i in new_list])
    logger.info("find_news: symbol=%s market=%s count=%d", symbol, market, len(new_list))
    return content_news, new_list


def get_hk_news_headlines(
    symbol: str,
    start_date: str,
    end_date: str,
) -> List[Dict[str, Any]]:
    """
    查询港股新闻标题。

    Args:
        symbol: 股票代码。
        start_date: 开始日期，格式 YYYY-MM-DD。
        end_date: 结束日期，格式 YYYY-MM-DD。

    Returns:
        List[Dict]: 港股新闻记录列表。
    """
    _, db = _init_db()
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        coll = db["hk_news_headlines_v2"]

        filter_dict = {
            "symbol": symbol,
            "fetched_at": {"$gte": start_dt, "$lte": end_dt},
        }

        cursor = coll.find(filter_dict).sort("trade_date", ASCENDING)
        records = [{k: v for k, v in doc.items() if k != "_id"} for doc in cursor]
        logger.info("get_hk_news_headlines: symbol=%s count=%d", symbol, len(records))
        return records
    except Exception as e:
        logger.exception("港股新闻查询错误: symbol=%s, error=%s", symbol, e)
        return []


def get_cn_news_headlines(
    symbol: str,
    start_date: str,
    end_date: str,
) -> List[Dict[str, Any]]:
    """
    查询 A 股新闻标题。

    Args:
        symbol: 股票代码。
        start_date: 开始日期，格式 YYYY-MM-DD。
        end_date: 结束日期，格式 YYYY-MM-DD。

    Returns:
        List[Dict]: A 股新闻记录列表。
    """
    _, db = _init_db()
    try:
        coll = db["cn_new_lines"]

        filter_dict = {
            "symbol": symbol,
            "upgrade_time": {"$gte": start_date, "$lte": end_date},
        }

        cursor = coll.find(filter_dict).sort("upgrade_time", ASCENDING)
        records = [{k: v for k, v in doc.items() if k != "_id"} for doc in cursor]
        logger.info("get_cn_news_headlines: symbol=%s count=%d", symbol, len(records))
        return records
    except Exception as e:
        logger.exception("A股新闻查询错误: symbol=%s, error=%s", symbol, e)
        return []


def get_stock_news(
    symbol: str,
    start_date: str,
    end_date: str,
) -> List[Dict[str, Any]]:
    """
    获取股票新闻数据。

    Args:
        symbol: 股票代码。
        start_date: 开始日期，格式 YYYY-MM-DD。
        end_date: 结束日期，格式 YYYY-MM-DD。

    Returns:
        List[Dict]: 新闻数据列表。
    """
    return _query_mongodb_news(symbol, start_date, end_date)


def get_market_news(
    start_date: str,
    end_date: str,
    news_type: str = "global",
) -> List[Dict[str, Any]]:
    """
    获取市场新闻数据。

    Args:
        start_date: 开始日期，格式 YYYY-MM-DD。
        end_date: 结束日期，格式 YYYY-MM-DD。
        news_type: 新闻类型，默认 'global'。

    Returns:
        List[Dict]: 市场新闻数据列表。
    """
    return _query_mongodb_market_news(start_date, end_date, news_type)
