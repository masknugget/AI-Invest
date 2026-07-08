import time
import pandas as pd

from datetime import datetime
from typing import List, Dict, Any, Optional, Union

from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.collection import Collection

from app.config.config import Config
from app.core.config import settings
from tradingagents.utils.indicators import add_all_indicators
import urllib.parse

__client = None


def _get_init_db():
    user = Config.user
    host = Config.host
    db = Config.db
    ca = Config.ca
    pwd = Config.pwd

    uri = f"mongodb://{urllib.parse.quote_plus(user)}:{urllib.parse.quote_plus(pwd)}@{host}:27017/{db}?replicaSet=rs0&readPreference=secondary"

    if ca is not None:
        client = MongoClient(
            uri,
            tls=True,
            tlsCAFile=ca,
            tlsAllowInvalidHostnames=True,  # 若证书仍不匹配，先测试用
            serverSelectionTimeoutMS=15000,
            connectTimeoutMS=15000,  # 5秒，建立连接超时
            socketTimeoutMS=15000,  # 10秒，读写超时
            waitQueueTimeoutMS=15000,  # 5秒，连接池等待超时
            maxPoolSize=50
        )
    else:
        client = MongoClient(
            uri,
            tlsAllowInvalidHostnames=True,  # 若证书仍不匹配，先测试用
            serverSelectionTimeoutMS=15000,
            connectTimeoutMS=15000,  # 5秒，建立连接超时
            socketTimeoutMS=15000,  # 10秒，读写超时
            waitQueueTimeoutMS=15000,  # 5秒，连接池等待超时
            maxPoolSize=50
        )
    print("初始化client成功")
    return client


def _init_db():
    global __client
    time_s = time.time()
    if __client is None:
        __client = _get_init_db()
    elif __client._closed:
        __client = _get_init_db()

    database = __client[Config.db]
    return __client, database


def log_chat_history(data: Dict[str, Any]) -> None:
    """
    保存 ChatTracker 的 to_dict() 数据到 MongoDB

    Args:
        data: ChatTracker.to_dict() 返回的字典，包含用户对话历史
    """
    client, db = _init_db()
    try:
        coll = db['chat_history']
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
    except Exception as e:
        print(f"保存对话日志失败: {e}")
    finally:
        pass


def get_chat_history(
    user_id: Union[str, int],
    conversation_id=None
) -> List[Dict[str, Any]]:
    """
    通过 user_id 和 conversation_id 查找 chat_history，按照 create_datetime 升序排序返回列表

    Args:
        user_id: 用户ID
        conversation_id: 对话ID

    Returns:
        List[Dict]: 聊天记录列表，按创建时间升序排列
    """
    client, db = _init_db()
    try:
        coll = db['chat_history']

        if user_id is None:
            return []

        if conversation_id is None:
            filter_dict = {
                "user_id": user_id,
            }
        else:
            filter_dict = {
                "user_id": user_id,
                "conversation_id": conversation_id,
            }

        cursor = coll.find(filter_dict).sort("create_datetime", ASCENDING)
        records = [{k: v for k, v in doc.items() if k != "_id"} for doc in cursor]

        return records
    except Exception as e:
        print(f"查询对话历史失败: {e}")
        return []
    finally:
        pass


def save_user_profile(user_id: Union[str, int], profile_data: Dict[str, Any]) -> Optional[str]:
    """
    保存用户画像到 MongoDB user_profiles 集合

    Args:
        user_id: 用户ID
        profile_data: LLM 生成的画像数据（含 generatedTags, summary, audit 等）

    Returns:
        str: 插入文档的 _id，失败返回 None
    """
    client, db = _init_db()
    try:
        coll = db['user_profiles']

        doc = {
            "user_id": user_id,
            "generatedTags": profile_data.get("generatedTags", []),
            "summary": profile_data.get("summary", {}),
            "audit": profile_data.get("audit", {}),
            "datetime": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "timestamp": datetime.now(),
        }

        result = coll.insert_one(doc)
        return str(result.inserted_id)
    except Exception as e:
        print(f"保存用户画像失败: {e}")
        return None
    finally:
        pass


def log_rec_history(data: Dict[str, Any]) -> None:
    """
    保存推荐历史记录到MongoDB

    Args:
        data: 推荐记录字典，包含用户推荐历史
    """
    client, db = _init_db()
    try:
        coll = db['rec_history']
        log_entry = {
            "timestamp": datetime.now(),
            "user_id": data.get("user_id"),
            "rec_content_ids": data.get("rec_content_ids"),
            "create_datetime": data.get("create_datetime"),
        }
        coll.insert_one(log_entry)
    except Exception as e:
        print(f"保存推荐日志失败: {e}")
    finally:
        pass

def get_rec_history(
    user_id: Union[str, int],
    conversation_id=None
) -> List[Dict[str, Any]]:
    """
    通过 user_id 和 conversation_id 查找 rec_history，按照 create_datetime 升序排序返回列表

    Args:
        user_id: 用户ID
        conversation_id: 对话ID

    Returns:
        List[Dict]: 推荐记录列表，按创建时间升序排列
    """
    client, db = _init_db()
    try:
        coll = db['rec_history']

        if user_id is None:
            return []

        if conversation_id is None:
            filter_dict = {
                "user_id": user_id,
            }
        else:
            filter_dict = {
                "user_id": user_id,
                "conversation_id": conversation_id,
            }

        cursor = coll.find(filter_dict).sort("create_datetime", DESCENDING)
        records = [{k: v for k, v in doc.items() if k != "_id"} for doc in cursor]

        rec_history = set()
        for i in records[:30]:
            if 'rec_content_ids' in i:
                ids = i['rec_content_ids']
                for j in ids:
                    rec_history.add(j)

        return list(rec_history)[:30]
    except Exception as e:
        print(f"查询推荐历史失败: {e}")
        return []
    finally:
        pass


def log_rec_content_history(user_id: Union[str, int], rec_content_data: List[Dict[str, Any]]) -> None:
    """
    保存推荐内容的完整数据到MongoDB

    Args:
        user_id: 用户ID
        rec_content_data: 推荐内容数据列表，包含每条推荐的完整信息
    """
    client, db = _init_db()
    try:
        coll = db['rec_content_history']
        log_entry = {
            "timestamp": datetime.now(),
            "user_id": user_id,
            "rec_content_data": rec_content_data,
            "create_datetime": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        coll.insert_one(log_entry)
    except Exception as e:
        print(f"保存推荐内容日志失败: {e}")
    finally:
        pass

def log_views_insight(user_id: Union[str, int], insight_id: str) -> None:
    """
    保存 Insight 浏览记录到 MongoDB

    Args:
        user_id: 用户ID
        insight_id: 浏览的 Insight ID
    """
    client, db = _init_db()
    try:
        coll = db['insight_views']
        log_entry = {
            "timestamp": datetime.now(),
            "user_id": user_id,
            "insight_id": insight_id,
            "create_datetime": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        coll.insert_one(log_entry)
    except Exception as e:
        print(f"保存浏览记录失败: {e}")
    finally:
        pass


def get_views_insight(
    user_id: Union[str, int],
    page_size: int = 20,
    page: int = 1
) -> Dict[str, Any]:
    """
    查询用户 Insight 浏览历史

    Args:
        user_id: 用户ID
        page_size: 每页数量
        page: 页码，从1开始

    Returns:
        Dict: 包含 items 和 pagination 的字典
    """
    client, db = _init_db()
    try:
        coll = db['insight_views']

        if user_id is None:
            return {
                "items": [],
                "pagination": {
                    "page": page,
                    "pageSize": page_size,
                    "total": 0,
                    "hasMore": False
                }
            }

        filter_dict = {"user_id": user_id}

        # 分页查询
        skip = (page - 1) * page_size
        cursor = coll.find(filter_dict).sort("timestamp", DESCENDING).skip(skip).limit(page_size)
        items = [{k: v for k, v in doc.items() if k != "_id"} for doc in cursor]

        # 去重
        df = pd.DataFrame(items)
        unique_df = df.drop_duplicates(subset='insight_id', keep='first')
        items = unique_df.to_dict('records')

        # 获取总数
        total = coll.count_documents(filter_dict)

        return {
            "items": items,
            "pagination": {
                "page": page,
                "pageSize": page_size,
                "total": total,
                "hasMore": total > skip + len(items),
            }
        }
    except Exception as e:
        print(f"查询浏览历史失败: {e}")
        return {
            "items": [],
            "pagination": {
                "page": page,
                "pageSize": page_size,
                "total": 0,
                "hasMore": False
            }
        }
    finally:
        # client.close()
        pass


def get_recommendation_history_docs(
    user_id: Union[str, int],
    page_size: int = 20,
    page: int = 1,
    action: Optional[str] = None
) -> Dict[str, Any]:
    """
    查询用户推荐内容历史记录（从 `rec_content_history` 集合）

    Args:
        user_id: 用户ID
        page_size: 每页数量
        page: 页码，从1开始
        action: 过滤特定动作：click/dismiss/share/save

    Returns:
        Dict: 包含 items 和 pagination 的字典
    """
    client, db = _init_db()
    try:
        coll = db['rec_content_history']

        # 构建查询条件
        query = {}
        if user_id is not None:
            query["user_id"] = user_id
        if action:
            query["action"] = action

        # 分页查询
        skip = (page - 1) * page_size
        cursor = coll.find(query).sort("timestamp", DESCENDING).skip(skip).limit(page_size)
        items = [{k: v for k, v in doc.items() if k != "_id"} for doc in cursor]

        # 获取总数
        total = coll.count_documents(query)

        return {
            "items": items,
            "pagination": {
                "page": page,
                "pageSize": page_size,
                "total": total,
                "hasMore": total > skip + len(items),
            }
        }
    except Exception as e:
        print(f"查询推荐历史失败: {e}")
        return {
            "items": [],
            "pagination": {"page": page, "pageSize": page_size, "total": 0, "hasMore": False}
        }
    finally:
        # client.close()
        pass


def get_insight_by_id(insight_id: str) -> Optional[Dict[str, Any]]:
    """
    根据 ID 从 MongoDB `insight_news` 集合查询单条洞察数据

    Args:
        insight_id: Insight ID (MongoDB _id 的字符串形式)

    Returns:
        Dict: 洞察数据，找不到返回 None
    """
    from bson import ObjectId

    client, db = _init_db()
    try:
        coll = db['insight_agg']
        try:
            obj_id = ObjectId(insight_id)
        except Exception:
            # 如果 insight_id 不是有效的 ObjectId，尝试用字符串匹配
            doc = coll.find_one({"article_id": insight_id})
            if doc:
                doc.pop("_id", None)
                return doc
            return None

        doc = coll.find_one({"_id": obj_id})
        if doc:
            doc.pop("_id", None)
            return doc
        return None
    except Exception as e:
        print(f"查询 Insight 失败: {e}")
        return None
    finally:
        # client.close()
        pass

def get_user_profile(user_id: Union[str, int]) -> Optional[Dict[str, Any]]:
    """
    获取用户最新画像

    从 MongoDB user_profiles 集合中，根据 user_id 获取最新的一条记录（按 datetime 降序）。

    Args:
        user_id: 用户ID

    Returns:
        Dict: 用户画像数据，找不到返回 None
    """
    client, db = _init_db()
    try:
        coll = db['user_profiles']

        doc = coll.find_one(
            {"user_id": user_id},
            sort=[("datetime", DESCENDING)]
        )

        if doc:
            doc.pop("_id", None)
            return doc
        return None
    except Exception as e:
        print(f"查询用户画像失败: {e}")
        return None
    finally:
        # client.close()
        pass


def find_qa_pair(uuid_str):
    client, db = _init_db()
    try:

        coll = db['qa_pair']
        docs = coll.find_one({"uuid": uuid_str})

        return docs
    except Exception as e:
        print(f"查询对话历史失败: {e}")
        return []
    finally:
        # client.close()
        pass


def del_user_conversation(
    user_id: Union[str, int],
    conversation_id: str
) -> bool:
    client, db = _init_db()
    try:
        coll = db['chat_history']

        if not user_id or not conversation_id:
            return False

        filter_dict = {
            "user_id": user_id,
            "conversation_id": conversation_id
        }

        result = coll.delete_many(filter_dict)
        return result.deleted_count > 0
    except Exception as e:
        print(f"删除对话失败: {e}")
        return False
    finally:
        # client.close()
        pass


def update_conversation_title(
    user_id: Union[str, int],
    conversation_id: str,
    title: str
) -> bool:
    client, db = _init_db()
    try:
        coll = db['chat_history']

        if not user_id or not conversation_id:
            return False

        filter_dict = {
            "user_id": user_id,
            "conversation_id": conversation_id
        }

        result = coll.find_one_and_update(
            filter_dict,
            {"$set": {"title": title}},
            sort=[("create_datetime", ASCENDING)],
            return_document=True
        )

        return result is not None
    except Exception as e:
        print(f"更新会话标题失败: {e}")
        return False
    finally:
        # client.close()
        pass


def get_symbol(
    symbol_name: str,
) -> Optional[Dict[str, Any]]:
    client, db = _init_db()
    try:
        col = db['stock_daily_basic']

        # 使用OR查询，匹配symbol或name任一字段
        filter_dict = {
            "$or": [
                {"symbol": symbol_name},
                {"name": symbol_name}
            ]
        }

        result = col.find_one(filter_dict, {"_id": 0})
        if result is None:
            # 如果没找到，返回空信息结构
            return {
                "symbol": "",
                "name": "",
            }
        return result
    except Exception as e:
        print(f"查询股票信息失败: {e}")
        return None
    finally:
        # client.close()
        pass

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

    collection_name_map = {
        "technical": settings.HK_SYNC_PRICE_COLLECTION,
        "basic": "stock_daily_basic",
    }
    collection_name = collection_name_map[data_type]
    return _query_mongodb(symbol, collection_name, start_date, end_date)


def get_stock_info(symbol: str) -> Optional[Dict[str, Any]]:
    client, db = _init_db()
    try:
        coll: Collection = db["stock_daily_basic"]
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
        # client.close()
        pass


def get_company_name(ticker: str):
    client, db = _init_db()
    coll: Collection = db["stock_daily_basic"]
    info = coll.find_one({"symbol": ticker}, {"_id": 0})
    # client.close()
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


def _query_mongodb(
    symbol: str,
    collection_name: str,
    start_date: str,
    end_date: str
) -> List[Dict[str, Any]]:
    client, db = _init_db()
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

        return records
    except Exception as e:
        print(f"MongoDB 查询错误: {e}")
        return []
    finally:
        # client.close()
        pass


def _query_mongodb_news(
    symbol: str,
    start_date: str,
    end_date: str
) -> List[Dict[str, Any]]:
    client, db = _init_db()
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        coll: Collection = db[settings.HK_SYNC_HEADLINE_COLLECTION]

        filter_dict = {
            "$or": [
                {"symbol": symbol},
                {"stock": symbol},
                {"ticker": symbol}
            ],
            "trade_date": {"$gte": start_dt, "$lte": end_dt},
        }

        cursor = coll.find(filter_dict).sort("trade_date", DESCENDING)
        records = [{k: v for k, v in doc.items() if k != "_id"} for doc in cursor]

        return records
    except Exception as e:
        print(f"新闻查询错误: {e}")
        return []
    finally:
        pass


def _query_mongodb_market_news(
    start_date: str,
    end_date: str,
    news_type: str = "global"
) -> List[Dict[str, Any]]:
    client, db = _init_db()
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        coll: Collection = db["market_news"]

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
        # client.close()
        pass


def convert_float(item_data):
    if hasattr(item_data, 'to_decimal'):
        return item_data.to_decimal()
    return item_data


def get_daily_performance(
    symbol,
    start_date,
    end_date,
    market: str = "HK"
):
    client, db = _init_db()

    if market == 'HK':
        col_name = 'hk_daily_performance'
    else:
        col_name = 'cn_daily_performance'
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
    df['close'] = df['close'].map(convert_float)
    df['close'] = df['close'].astype(float)

    df = add_all_indicators(df)

    col = ['trade_date', 'ma5', 'ma10', 'ma20', 'ma60', 'rsi', 'macd_dif', 'macd_dea', 'macd', 'boll_mid', 'boll_upper',
           'boll_lower']
    col_num = ['ma5', 'ma10', 'ma20', 'ma60', 'rsi', 'macd_dif', 'macd_dea', 'macd', 'boll_mid', 'boll_upper',
               'boll_lower']
    df[col_num] = df[col_num].round(2)
    df = df.tail(60)
    df = df.ffill()
    df_data = df.to_dict('list')

    tmp_data = ["""
    技术指标数据，trade_date为日期，close为收盘价，
    'ma5', 'ma10', 'ma20', 'ma60' 为均线系统

    """]
    for key in col:
        value = df_data[key]
        if key == 'trade_date':
            value = [i.strftime("%Y%m%d") for i in value]
        else:
            value = [str(i) for i in value]
        value_str = " ".join(value)
        line_content = key + ": " + value_str
        tmp_data.append(line_content)

    content = "\n".join(tmp_data)
    return content, df_data


def search_symbol(
        symbol_name: str,
) -> Optional[Dict[str, Any]]:
    client, db = _init_db()
    try:
        col = db['hk_symbol_name']
        # 使用OR查询，匹配symbol或name任一字段
        filter_dict = {
            "$or": [
                {"symbol": symbol_name},
                {"productSecondName": symbol_name},
                {"ric": symbol_name},
            ]
        }

        result = col.find_one(filter_dict, {"_id": 0})
        if result is None:
            # 如果没找到，返回空信息结构
            return {
                "symbol": "",
                "name": "",
                "productSecondName": "",
                "market": ""
            }

        return result
    except Exception as e:
        print(f"查询股票信息失败: {e}")
        return None
    finally:
        pass


def get_business_desc(symbol_name):
    """

    :param symbol_name:
    :return:
    """
    client, db = _init_db()
    try:
        col = db['hk_business_desc_v2']
        filter_dict = {
            "$or": [
                {"symbol": symbol_name},
            ]
        }
        result = col.find_one(filter_dict, {"_id": 0})
        if result is None:
            desc = ""
        else:
            if isinstance(result, dict) and 'desc' in result:
                desc = result['desc']
            else:
                desc = ""
        return desc
    except Exception as e:
        print(e)
        return ""


def convert_data(item):
    return float(item.to_decimal())


def get_stock_daily_basic(
        symbol: str,
        start_date: str,
        end_date: str,
):
    """
    根据 symbol + 交易日期区间 查询日线数据（基础数据）
    保留向后兼容
    """
    data = get_stock_data(symbol, start_date, end_date, "technical")

    df = pd.DataFrame(data)
    df['close'] = df['close'].map(convert_data)
    df = add_all_indicators(df)

    col = ['trade_date', 'pb', 'pct_chg', 'pe_ttm', 'ps_ttm', ]
    col_num = ['pb', 'pct_chg', 'pe_ttm', 'ps_ttm', ]
    df[col_num] = df[col_num].round(2)
    df = df.tail(60)
    df_data = df.to_dict('list')

    data = ["""
    基本面指标数据: pb, pe_ttm, ps_ttm
    pct_chg为涨幅
    """]
    for key in col:
        value = df_data[key]
        if key == 'trade_date':
            value = [i.strftime("%Y%m%d") for i in value]
        else:
            value = [str(i) for i in value]
        value_str = " ".join(value)
        line_content = key + ": " + value_str
        data.append(line_content)

    content = "\n".join(data)
    return content, df_data



def get_stock_daily_technical(
    symbol: str,
    start_date: str,
    end_date: str,
):
    """
    :param symbol:
    :param start_date:
    :param end_date:
    :return:
    """
    data = get_stock_data(symbol, start_date, end_date, "technical")
    df = pd.DataFrame(data)
    df['close'] = df['close'].map(convert_data)
    df = add_all_indicators(df)

    col = ['trade_date', 'ma5', 'ma10', 'ma20', 'ma60', 'rsi', 'macd_dif', 'macd_dea', 'macd', 'boll_mid', 'boll_upper',
           'boll_lower']
    col_num = ['ma5', 'ma10', 'ma20', 'ma60', 'rsi', 'macd_dif', 'macd_dea', 'macd', 'boll_mid', 'boll_upper',
               'boll_lower']

    df[col_num] = df[col_num].round(2)
    df = df.tail(60)
    df_data = df.to_dict('list')

    tmp_data = ["""
    技术指标数据, trade_date为日期, close为收盘价,
    'ma5', 'ma10', 'ma20', 'ma60' 为均线系统
    """]

    for key in col:
        value = df_data[key]
        if key == 'trade_date':
            value = [i.strftime("%Y%m%d") for i in value]
        else:
            value = [str(i) for i in value]
        value_str = " ".join(value)
        line_content = key + ": " + value_str
        tmp_data.append(line_content)

    content = "\n".join(tmp_data)
    return content, df_data


def get_hk_news_headlines(
    symbol,
    start_date,
    end_date
):
    client, db = _init_db()
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

        return records
    except Exception as e:
        print(f"MongoDB 查询错误: {e}")
        return []
    finally:
        # client.close()
        pass


def get_cn_news_headlines(
    symbol,
    start_date,
    end_date
):
    client, db = _init_db()
    try:
        # start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        # end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        coll = db["cn_new_lines"]

        filter_dict = {
            "symbol": symbol,
            "upgrade_time": {"$gte": start_date, "$lte": end_date},
        }

        cursor = coll.find(filter_dict).sort("upgrade_time", ASCENDING)
        records = [{k: v for k, v in doc.items() if k != "_id"} for doc in cursor]

        return records
    except Exception as e:
        print(f"MongoDB 查询错误: {e}")
        return []
    finally:
        # client.close()
        pass


def parse_news(data_item):
    """
    新闻
    :param data_item:
    :return:
    """
    head_line = data_item.get("headline")
    brief = data_item.get("brief")

    content = f"""title: {head_line}
{brief}
"""

    return content


def find_news(
        symbol="00467",
        start_date="2025-01-01",
        end_date="2026-04-01",
        market: str = 'HK'
):
    """

    :param symbol:
    :param start_date:
    :param end_date:
    :param market:
    :return:
    """
    if market == 'HK':
        data = get_hk_news_headlines(
            symbol,
            start_date,
            end_date
        )
    else:
        data = get_cn_news_headlines(
            symbol,
            start_date,
            end_date
        )
    if len(data) == 0:
        return "没有新闻数据", data

    if isinstance(data, list):
        data = data[0]

    new_list = []
    if 'raw_data' in data:
        raw_data = data['raw_data']
        new_list = raw_data['newsList']
    elif 'newList' in data:
        new_list = data['newList']

    content_news = "\n".join([parse_news(i) for i in new_list])

    return content_news, new_list


def get_symbol_info(
        symbol: str,
        start_date="2025-01-01",
        end_date="2026-04-01"
):
    client, db = _init_db()

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
            'productSecondName': record['productSecondName'],
            'open': record['open'],
            'high': record['high'],
            'low': record['low'],
            'close': record['close'],
        }
    else:
        out_data = {
            "symbol": symbol,
            "business_desc": company_des,
        }

    return out_data


def get_fin_report(
    symbol='00001',
    state_period_start=2023,
    state_period_end=2025,
    market: str = "HK"
):
    """
    :param symbol:
    :param state_period_end:
    :param state_period_start:
    :param market:
    :return:
    """
    client, db = _init_db()

    if market == 'HK':
        col_name_inc = 'hk_fin_reports_inc'
        col_name_cas = 'hk_fin_reports_cas'
        col_name_bal = 'hk_fin_reports_bal'
    else:
        col_name_inc = 'cn_fin_reports_inc'
        col_name_cas = 'cn_fin_reports_cas'
        col_name_bal = 'cn_fin_reports_bal'
    # 选择名字
    col_inc = db[col_name_inc]
    col_cas = db[col_name_cas]
    col_bal = db[col_name_bal]

    filter_dict = {
        "symbol": symbol,
        "statementPeriod": {"$gte": state_period_start, "$lte": state_period_end},
    }

    # inc 财报解析
    cursor = col_inc.find(filter_dict)
    records_inc = [{k: v for k, v in doc.items() if k != "_id"} for doc in cursor]
    md_inc, report_inc = parse_report(records_inc)

    # cas 解析
    cursor = col_cas.find(filter_dict)
    records_cas = [{k: v for k, v in doc.items() if k != "_id"} for doc in cursor]
    md_cas, report_cas = parse_report(records_cas)

    cursor = col_bal.find(filter_dict)
    records_bal = [{k: v for k, v in doc.items() if k != "_id"} for doc in cursor]
    md_bal, report_bal = parse_report(records_bal)

    md_report = str(md_bal) + '\n' + str(md_inc) + '\n' + str(md_cas)
    data_out = {
        'data_inc': report_inc,
        'data_cas': report_cas,
        'data_bal': report_bal,
    }

    return md_report, data_out


def parse_report(records_filter):
    """
    :param records_filter:
    :return:
    """
    data_2025 = [i for i in records_filter if i['statementPeriod'] == 2025]
    data_2024 = [i for i in records_filter if i['statementPeriod'] == 2024]
    data_2023 = [i for i in records_filter if i['statementPeriod'] == 2023]

    df = pd.concat([pd.DataFrame(data_2025), pd.DataFrame(data_2024), pd.DataFrame(data_2023)])
    df = df[['name', 'statementPeriod', 'value']]

    pivot_df = df.pivot(index='name', columns='statementPeriod', values='value')

    new_order = [i.get('name') for i in data_2023]  # 你的新索引顺序
    pivot_df = pivot_df.loc[new_order]
    pivot_df = pivot_df.fillna(0)

    out_list = []
    for name, item in pivot_df.iterrows():
        dt = {str(k): v for k, v in item.to_dict().items()}
        tmp = {'name': name, **dt}
        out_list.append(tmp)

    md_data = pivot_df.to_markdown()
    return md_data, out_list
