from datetime import datetime
from typing import List, Dict, Any, Optional, Union
import pandas as pd
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database

# -------------------- 参数 --------------------
MONGO_URI = "mongodb://localhost:27017"


# ==================== 市场识别函数 ====================

def detect_market(symbol: str) -> str:
    """
    自动识别股票所属市场
    
    Args:
        symbol: 股票代码或代码+市场后缀
        
    Returns:
        str: 市场标识 'cn' | 'hk' | 'us' | 'unknown'
    """
    symbol_upper = symbol.upper().strip()

    # 港股（HKEX）
    if symbol_upper.endswith('.HK'):
        return 'hk'

    # 美股（常见后缀）
    if any(symbol_upper.endswith(suffix) for suffix in ['.US', '.NYSE', '.NASDAQ']):
        return 'us'

    # A股（纯数字代码）
    if symbol_upper.isdigit():
        if len(symbol_upper) == 6:
            prefix = symbol_upper[:3]
            if prefix in ['600', '601', '603', '605', '688']:  # 上海主板/科创板
                return 'cn'
            if prefix in ['000', '001', '002', '003', '300']:  # 深圳主板/创业板
                return 'cn'

    # 不包含后缀的美股代码（如 AAPL, TSLA）
    if symbol_upper.isalpha() and 1 <= len(symbol_upper) <= 5:
        return 'us'

    return 'unknown'


# ==================== 统一数据入口 ====================

def get_stock_data(
        symbol: str,
        start_date: str,
        end_date: str,
        data_type: str = "technical"
) -> List[Dict[str, Any]]:
    """
    统一股票数据获取入口
    
    Args:
        symbol: 股票代码
        start_date: 开始日期，格式：YYYY-MM-DD
        end_date: 结束日期，格式：YYYY-MM-DD
        data_type: 数据类型，'technical' 或 'basic'
        
    Returns:
        List[Dict]: 股票日线数据列表
    """
    if data_type not in ["technical", "basic"]:
        raise ValueError(f"不支持的 data_type: {data_type}")

    collection_name = f"stock_daily_{data_type}"
    return _query_mongodb(symbol, collection_name, start_date, end_date)


def get_stock_info(symbol: str) -> Optional[Dict[str, Any]]:
    """
    获取股票基本信息
    
    Args:
        symbol: 股票代码
        
    Returns:
        Dict: 股票基本信息，包含 name, industry, area, list_date 等
    """
    client = MongoClient(MONGO_URI)
    try:
        coll: Collection = client["stock_db"]["stock_daily_basic"]
        info = coll.find_one({"symbol": symbol}, {"_id": 0})

        if not info:
            result = {
                "name": "",
                "area": "",
                "industry": "",
                "market": "HK",
                "list_date": "",
                "current_price": "",
                "change_pct": "",
                "volume": "",
            }
            return result

        if info:
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
    finally:
        client.close()


def get_company_name(ticker: str):
    client = MongoClient(MONGO_URI)
    coll: Collection = client["stock_db"]["stock_daily_basic"]
    info = coll.find_one({"symbol": ticker}, {"_id": 0})

    if info is not None:
        company_name = info["name"]
        return company_name
    return ticker


def get_stock_news(
        symbol: str,
        start_date: str,
        end_date: str
) -> List[Dict[str, Any]]:
    """
    获取股票新闻数据
    
    Args:
        symbol: 股票代码
        start_date: 开始日期，格式：YYYY-MM-DD
        end_date: 结束日期，格式：YYYY-MM-DD
        
    Returns:
        List[Dict]: 新闻数据列表
    """
    return _query_mongodb_news(symbol, start_date, end_date)


def get_market_news(
        start_date: str,
        end_date: str,
        news_type: str = "global"
) -> List[Dict[str, Any]]:
    """
    获取市场新闻（全球、宏观、行业）
    
    Args:
        start_date: 开始日期
        end_date: 结束日期
        news_type: 新闻类型 'global' | 'macro' | 'industry'
        
    Returns:
        List[Dict]: 新闻列表
    """
    return _query_mongodb_market_news(start_date, end_date, news_type)


# ==================== 市场专用函数（向后兼容） ====================

def get_china_stock_data(
        symbol: str,
        start_date: str,
        end_date: str,
        data_type: str = "technical"
) -> List[Dict[str, Any]]:
    """A股数据查询"""
    return get_stock_data(symbol, start_date, end_date, data_type)


def get_hk_stock_data(
        symbol: str,
        start_date: str,
        end_date: str,
        data_type: str = "technical"
) -> List[Dict[str, Any]]:
    """港股数据查询"""
    return get_stock_data(symbol, start_date, end_date, data_type)


def get_china_stock_info(symbol: str) -> Optional[Dict[str, Any]]:
    """A股基本信息"""
    return get_stock_info(symbol)


def get_hk_stock_info(symbol: str) -> Optional[Dict[str, Any]]:
    """港股基本信息"""
    return get_stock_info(symbol)


# ==================== 数据查询实现 ====================

def _query_mongodb(
        symbol: str,
        collection_name: str,
        start_date: str,
        end_date: str
) -> List[Dict[str, Any]]:
    """
    MongoDB 统一查询函数
    
    Args:
        symbol: 股票代码
        collection_name: 集合名称
        start_date: 开始日期
        end_date: 结束日期
        
    Returns:
        List[Dict]: 查询结果列表
    """
    client = MongoClient(MONGO_URI)
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        coll: Collection = client["stock_db"][collection_name]

        filter_dict = {
            "symbol": symbol,
            "trade_date": {"$gte": start_dt, "$lte": end_dt},
        }

        cursor = coll.find(filter_dict).sort("trade_date", ASCENDING)
        records = [{k: v for k, v in doc.items() if k != "_id"} for doc in cursor]

        return records
    except Exception as e:
        print(f"MongoDB 查询错误: {e}")
        return []
    finally:
        client.close()


def _query_mongodb_news(
        symbol: str,
        start_date: str,
        end_date: str
) -> List[Dict[str, Any]]:
    """
    新闻数据查询
    
    Args:
        symbol: 股票代码
        start_date: 开始日期
        end_date: 结束日期
        
    Returns:
        List[Dict]: 新闻列表
    """
    client = MongoClient(MONGO_URI)
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        coll: Collection = client["stock_db"]["stock_news"]

        filter_dict = {
            "$or": [
                {"symbol": symbol},
                {"stock": symbol},
                {"ticker": symbol}
            ],
            "date": {"$gte": start_dt, "$lte": end_dt},
        }

        cursor = coll.find(filter_dict).sort("date", DESCENDING)
        records = [{k: v for k, v in doc.items() if k != "_id"} for doc in cursor]

        return records
    except Exception as e:
        print(f"新闻查询错误: {e}")
        return []
    finally:
        client.close()


def _query_mongodb_market_news(
        start_date: str,
        end_date: str,
        news_type: str = "global"
) -> List[Dict[str, Any]]:
    """
    市场新闻查询
    
    Args:
        start_date: 开始日期
        end_date: 结束日期
        news_type: 新闻类型
        
    Returns:
        List[Dict]: 新闻列表
    """
    client = MongoClient(MONGO_URI)
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        coll: Collection = client["stock_db"]["market_news"]

        filter_dict = {
            "date": {"$gte": start_dt, "$lte": end_dt},
        }

        if news_type != "global":
            filter_dict["type"] = news_type

        cursor = coll.find(filter_dict).sort("date", DESCENDING)
        records = [{k: v for k, v in doc.items() if k != "_id"} for doc in cursor]

        return records
    except Exception as e:
        print(f"市场新闻查询错误: {e}")
        return []
    finally:
        client.close()


# ==================== 原有的两个函数（保留向后兼容） ====================

def get_stock_daily_technical(
        symbol: str,
        start_date: str,
        end_date: str,
) -> List[Dict[str, Any]]:
    """
    根据 symbol + 交易日期区间 查询日线数据（技术指标）
    保留向后兼容
    """
    return get_stock_data(symbol, start_date, end_date, "technical")


def get_stock_daily_basic(
        symbol: str,
        start_date: str,
        end_date: str,
) -> List[Dict[str, Any]]:
    """
    根据 symbol + 交易日期区间 查询日线数据（基础数据）
    保留向后兼容
    """
    return get_stock_data(symbol, start_date, end_date, "basic")
