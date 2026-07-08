import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import pandas as pd
from pymongo import ASCENDING
from pymongo.collection import Collection

from app.core.config import settings
from app.core.db.connection import _init_db
from tradingagents.utils.indicators import add_all_indicators

# 简单日志：模块名作为 logger 名，便于追踪
logger = logging.getLogger(__name__)


def convert_float(item_data: Any) -> Any:
    """兼容 MongoDB Decimal128 类型转换为 Python Decimal。"""
    if hasattr(item_data, "to_decimal"):
        return item_data.to_decimal()
    return item_data


def convert_data(item: Any) -> float:
    """将 Decimal128 或数字转换为 float。"""
    return float(item.to_decimal())


def get_symbol(symbol_name: str) -> Optional[Dict[str, Any]]:
    """
    根据 symbol 或 name 从 stock_daily_basic 集合查询单条股票信息。

    Args:
        symbol_name: 股票代码或名称。

    Returns:
        Optional[Dict]: 股票信息字典；未找到返回空结构，异常返回 None。
    """
    # client 由 _init_db 作为单例管理，此处仅取出 db 使用
    _, db = _init_db()
    try:
        col = db["stock_daily_basic"]

        # 使用 OR 查询，匹配 symbol 或 name 任一字段
        filter_dict = {
            "$or": [
                {"symbol": symbol_name},
                {"name": symbol_name},
            ]
        }

        result = col.find_one(filter_dict, {"_id": 0})
        if result is None:
            logger.info("get_symbol: symbol_name=%s not found", symbol_name)
            return {"symbol": "", "name": ""}

        logger.info("get_symbol: symbol_name=%s found", symbol_name)
        return result
    except Exception as e:
        logger.exception("查询股票信息失败: symbol_name=%s, error=%s", symbol_name, e)
        return None


def get_stock_data(
    symbol: str,
    start_date: str,
    end_date: str,
    data_type: str = "technical",
) -> List[Dict[str, Any]]:
    """
    统一股票数据获取入口。

    Args:
        symbol: 股票代码。
        start_date: 开始日期，格式 YYYY-MM-DD。
        end_date: 结束日期，格式 YYYY-MM-DD。
        data_type: 数据类型，'technical' 或 'basic'。

    Returns:
        List[Dict]: 股票日线数据列表。
    """
    if data_type not in ["technical", "basic"]:
        raise ValueError(f"不支持的 data_type: {data_type}")

    collection_name_map = {
        "technical": getattr(settings, "HK_SYNC_PRICE_COLLECTION", "hk_sync_price"),
        "basic": "stock_daily_basic",
    }
    collection_name = collection_name_map[data_type]
    return _query_mongodb(symbol, collection_name, start_date, end_date)


def get_stock_info(symbol: str) -> Optional[Dict[str, Any]]:
    """
    查询股票基本信息。

    Args:
        symbol: 股票代码。

    Returns:
        Optional[Dict]: 包含 name、area、industry 等字段的字典。
    """
    _, db = _init_db()
    try:
        coll: Collection = db["stock_daily_basic"]
        info = coll.find_one({"symbol": symbol}, {"_id": 0})

        if not info:
            logger.info("get_stock_info: symbol=%s not found", symbol)
            return {
                "name": "",
                "area": "",
                "industry": "",
                "market": "HK",
                "list_date": "",
                "current_price": "",
                "change_pct": "",
                "volume": "",
            }

        return {
            "name": info.get("name", ""),
            "area": info.get("city", ""),
            "industry": info.get("industry", ""),
            "market": "HK",
            "list_date": info.get("ipo_date", ""),
            "current_price": info.get("bps", ""),
            "change_pct": info.get("pe_ttm", ""),
            "volume": info.get("total_shares", ""),
        }
    except Exception as e:
        logger.exception("查询股票信息失败: symbol=%s, error=%s", symbol, e)
        return None


def get_company_name(ticker: str) -> str:
    """
    根据股票代码查询公司名称。

    Args:
        ticker: 股票代码。

    Returns:
        str: 公司名称；未找到返回原代码。
    """
    _, db = _init_db()
    try:
        coll: Collection = db["stock_daily_basic"]
        info = coll.find_one({"symbol": ticker}, {"_id": 0, "name": 1})
        if info is not None and "name" in info:
            return info["name"]
    except Exception as e:
        logger.exception("查询公司名称失败: ticker=%s, error=%s", ticker, e)

    return ticker


# ==================== 市场专用函数（向后兼容） ====================


def get_china_stock_data(
    symbol: str,
    start_date: str,
    end_date: str,
    data_type: str = "technical",
) -> List[Dict[str, Any]]:
    """A股数据查询。"""
    return get_stock_data(symbol, start_date, end_date, data_type)


def get_hk_stock_data(
    symbol: str,
    start_date: str,
    end_date: str,
    data_type: str = "technical",
) -> List[Dict[str, Any]]:
    """港股数据查询。"""
    return get_stock_data(symbol, start_date, end_date, data_type)


def get_china_stock_info(symbol: str) -> Optional[Dict[str, Any]]:
    """A股基本信息。"""
    return get_stock_info(symbol)


def get_hk_stock_info(symbol: str) -> Optional[Dict[str, Any]]:
    """港股基本信息。"""
    return get_stock_info(symbol)


def _query_mongodb(
    symbol: str,
    collection_name: str,
    start_date: str,
    end_date: str,
) -> List[Dict[str, Any]]:
    """
    内部查询函数：按 symbol 和 trade_date 区间查询指定集合。

    Args:
        symbol: 股票代码。
        collection_name: MongoDB 集合名。
        start_date: 开始日期，格式 YYYY-MM-DD。
        end_date: 结束日期，格式 YYYY-MM-DD。

    Returns:
        List[Dict]: 查询结果列表，不含 _id 字段。
    """
    _, db = _init_db()
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        coll: Collection = db[collection_name]
        filter_dict = {
            "symbol": symbol,
            "trade_date": {"$gte": start_dt, "$lte": end_dt},
        }

        cursor = coll.find(filter_dict).sort("trade_date", ASCENDING)
        records = [{k: v for k, v in doc.items() if k != "_id"} for doc in cursor]
        logger.info(
            "_query_mongodb: symbol=%s collection=%s count=%d",
            symbol,
            collection_name,
            len(records),
        )
        return records
    except Exception as e:
        logger.exception(
            "MongoDB 查询错误: symbol=%s collection=%s, error=%s",
            symbol,
            collection_name,
            e,
        )
        return []


def get_daily_performance(
    symbol: str,
    start_date: str,
    end_date: str,
    market: str = "HK",
) -> tuple:
    """
    查询每日表现数据并计算技术指标，返回文本与字典两种格式。

    Args:
        symbol: 股票代码。
        start_date: 开始日期，格式 YYYY-MM-DD。
        end_date: 结束日期，格式 YYYY-MM-DD。
        market: 市场，'HK' 或 'CN'。

    Returns:
        tuple: (文本描述字符串, 指标字典)。
    """
    _, db = _init_db()
    try:
        col_name = "hk_daily_performance" if market == "HK" else "cn_daily_performance"
        coll = db[col_name]

        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        filter_dict = {
            "symbol": symbol,
            "trade_date": {"$gte": start_dt, "$lte": end_dt},
        }
        cursor = coll.find(filter_dict).sort("trade_date", ASCENDING)
        records = [{k: v for k, v in doc.items() if k != "_id"} for doc in cursor]

        df = pd.DataFrame(records)
        if df.empty:
            logger.warning("get_daily_performance: symbol=%s market=%s no data", symbol, market)
            return "", {}

        df["close"] = df["close"].map(convert_float)
        df["close"] = df["close"].astype(float)

        df = add_all_indicators(df)

        col = [
            "trade_date", "ma5", "ma10", "ma20", "ma60", "rsi",
            "macd_dif", "macd_dea", "macd", "boll_mid", "boll_upper", "boll_lower",
        ]
        col_num = [
            "ma5", "ma10", "ma20", "ma60", "rsi",
            "macd_dif", "macd_dea", "macd", "boll_mid", "boll_upper", "boll_lower",
        ]
        df[col_num] = df[col_num].round(2)
        df = df.tail(60)
        df = df.ffill()
        df_data = df.to_dict("list")

        tmp_data = ["""
    技术指标数据，trade_date为日期，close为收盘价，
    'ma5', 'ma10', 'ma20', 'ma60' 为均线系统
    """]
        for key in col:
            value = df_data[key]
            if key == "trade_date":
                value = [i.strftime("%Y%m%d") for i in value]
            else:
                value = [str(i) for i in value]
            value_str = " ".join(value)
            line_content = key + ": " + value_str
            tmp_data.append(line_content)

        content = "\n".join(tmp_data)
        logger.info(
            "get_daily_performance: symbol=%s market=%s records=%d",
            symbol,
            market,
            len(df),
        )
        return content, df_data
    except Exception as e:
        logger.exception(
            "查询每日表现失败: symbol=%s market=%s, error=%s",
            symbol,
            market,
            e,
        )
        return "", {}


def search_symbol(symbol_name: str) -> Optional[Dict[str, Any]]:
    """
    根据 symbol、productSecondName 或 ric 查询港股股票信息。

    Args:
        symbol_name: 查询关键词。

    Returns:
        Optional[Dict]: 股票信息字典；未找到返回空结构，异常返回 None。
    """
    _, db = _init_db()
    try:
        col = db["hk_symbol_name"]
        # 使用 OR 查询，匹配 symbol、productSecondName 或 ric 任一字段
        filter_dict = {
            "$or": [
                {"symbol": symbol_name},
                {"productSecondName": symbol_name},
                {"ric": symbol_name},
            ]
        }

        result = col.find_one(filter_dict, {"_id": 0})
        if result is None:
            logger.info("search_symbol: symbol_name=%s not found", symbol_name)
            return {
                "symbol": "",
                "name": "",
                "productSecondName": "",
                "market": "",
            }

        logger.info("search_symbol: symbol_name=%s found", symbol_name)
        return result
    except Exception as e:
        logger.exception("查询股票信息失败: symbol_name=%s, error=%s", symbol_name, e)
        return None


def get_business_desc(symbol_name: str) -> str:
    """
    查询港股业务描述。

    Args:
        symbol_name: 股票代码或名称。

    Returns:
        str: 业务描述字符串；未找到或异常返回空字符串。
    """
    _, db = _init_db()
    try:
        col = db["hk_business_desc_v2"]
        filter_dict = {"symbol": symbol_name}
        result = col.find_one(filter_dict, {"_id": 0})

        if isinstance(result, dict) and "desc" in result:
            return result["desc"]

        return ""
    except Exception as e:
        logger.exception("查询业务描述失败: symbol_name=%s, error=%s", symbol_name, e)
        return ""


def get_stock_daily_basic(
    symbol: str,
    start_date: str,
    end_date: str,
) -> tuple:
    """
    根据 symbol + 交易日期区间查询日线基础数据，并计算基本面指标。

    Args:
        symbol: 股票代码。
        start_date: 开始日期，格式 YYYY-MM-DD。
        end_date: 结束日期，格式 YYYY-MM-DD。

    Returns:
        tuple: (文本描述字符串, 指标字典)。
    """
    data = get_stock_data(symbol, start_date, end_date, "technical")

    df = pd.DataFrame(data)
    if df.empty:
        logger.warning("get_stock_daily_basic: symbol=%s no data", symbol)
        return "", {}

    df["close"] = df["close"].map(convert_data)
    df = add_all_indicators(df)

    col = ["trade_date", "pb", "pct_chg", "pe_ttm", "ps_ttm"]
    col_num = ["pb", "pct_chg", "pe_ttm", "ps_ttm"]
    df[col_num] = df[col_num].round(2)
    df = df.tail(60)
    df_data = df.to_dict("list")

    data_text = ["""
    基本面指标数据: pb, pe_ttm, ps_ttm
    pct_chg为涨幅
    """]
    for key in col:
        value = df_data[key]
        if key == "trade_date":
            value = [i.strftime("%Y%m%d") for i in value]
        else:
            value = [str(i) for i in value]
        value_str = " ".join(value)
        line_content = key + ": " + value_str
        data_text.append(line_content)

    content = "\n".join(data_text)
    return content, df_data


def get_stock_daily_technical(
    symbol: str,
    start_date: str,
    end_date: str,
) -> tuple:
    """
    根据 symbol + 交易日期区间查询日线数据，并计算技术指标。

    Args:
        symbol: 股票代码。
        start_date: 开始日期，格式 YYYY-MM-DD。
        end_date: 结束日期，格式 YYYY-MM-DD。

    Returns:
        tuple: (文本描述字符串, 指标字典)。
    """
    data = get_stock_data(symbol, start_date, end_date, "technical")
    df = pd.DataFrame(data)
    if df.empty:
        logger.warning("get_stock_daily_technical: symbol=%s no data", symbol)
        return "", {}

    df["close"] = df["close"].map(convert_data)
    df = add_all_indicators(df)

    col = [
        "trade_date", "ma5", "ma10", "ma20", "ma60", "rsi",
        "macd_dif", "macd_dea", "macd", "boll_mid", "boll_upper", "boll_lower",
    ]
    col_num = [
        "ma5", "ma10", "ma20", "ma60", "rsi",
        "macd_dif", "macd_dea", "macd", "boll_mid", "boll_upper", "boll_lower",
    ]

    df[col_num] = df[col_num].round(2)
    df = df.tail(60)
    df_data = df.to_dict("list")

    tmp_data = ["""
    技术指标数据, trade_date为日期, close为收盘价,
    'ma5', 'ma10', 'ma20', 'ma60' 为均线系统
    """]

    for key in col:
        value = df_data[key]
        if key == "trade_date":
            value = [i.strftime("%Y%m%d") for i in value]
        else:
            value = [str(i) for i in value]
        value_str = " ".join(value)
        line_content = key + ": " + value_str
        tmp_data.append(line_content)

    content = "\n".join(tmp_data)
    return content, df_data


def get_symbol_info(
    symbol: str,
    start_date: str = "2025-01-01",
    end_date: str = "2026-04-01",
) -> Dict[str, Any]:
    """
    查询 symbol 最新日行情与业务描述。

    Args:
        symbol: 股票代码。
        start_date: 开始日期，格式 YYYY-MM-DD。
        end_date: 结束日期，格式 YYYY-MM-DD。

    Returns:
        Dict: 包含 symbol、business_desc、productSecondName、OHLC 等字段的字典。
    """
    _, db = _init_db()
    try:
        coll = db["hk_daily_performance"]

        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        filter_dict = {
            "symbol": symbol,
            "trade_date": {"$gte": start_dt, "$lte": end_dt},
        }

        cursor = coll.find(filter_dict).sort("trade_date", ASCENDING)
        records = [{k: v for k, v in doc.items() if k != "_id"} for doc in cursor]

        company_des = get_business_desc(symbol)
        if len(records) > 0:
            record = records[-1]
            out_data = {
                "symbol": symbol,
                "business_desc": company_des,
                "productSecondName": record.get("productSecondName"),
                "open": record.get("open"),
                "high": record.get("high"),
                "low": record.get("low"),
                "close": record.get("close"),
            }
        else:
            out_data = {
                "symbol": symbol,
                "business_desc": company_des,
            }

        logger.info("get_symbol_info: symbol=%s records=%d", symbol, len(records))
        return out_data
    except Exception as e:
        logger.exception("查询 symbol 信息失败: symbol=%s, error=%s", symbol, e)
        return {"symbol": symbol, "business_desc": ""}
