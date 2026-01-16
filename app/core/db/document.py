from datetime import datetime
from typing import List, Dict, Any

from pymongo import MongoClient, ASCENDING
from pymongo.collection import Collection

# -------------------- 参数 --------------------
MONGO_URI = "mongodb://localhost:27017"



def get_stock_daily_technical(
    symbol: str,
    start_date: str,  # 格式：YYYY-MM-DD
    end_date: str,    # 格式：YYYY-MM-DD
) -> List[Dict[str, Any]]:
    """
    根据 symbol + 交易日期区间 查询日线数据
    """
    client = MongoClient(MONGO_URI)
    coll: Collection = client["stock_db"]["stock_daily_technical"]

    # 字符串转 datetime
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    # 组装查询条件
    filter_dict = {
        "symbol": symbol,
        "trade_date": {"$gte": start_dt, "$lte": end_dt},
    }

    # 按需排序：先日期升序
    cursor = coll.find(filter_dict).sort("trade_date", ASCENDING)

    # 把 _id 去掉，方便后续直接 df = pd.DataFrame(list(records))
    records = [{k: v for k, v in doc.items() if k != "_id"} for doc in cursor]

    client.close()
    return records



def get_stock_daily_basic(
    symbol: str,
    start_date: str,  # 格式：YYYY-MM-DD
    end_date: str,    # 格式：YYYY-MM-DD
) -> List[Dict[str, Any]]:
    """
    根据 symbol + 交易日期区间 查询日线数据
    """
    client = MongoClient(MONGO_URI)
    coll: Collection = client["stock_db"]["stock_daily_basic"]

    # 字符串转 datetime
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    # 组装查询条件
    filter_dict = {
        "symbol": symbol,
        "trade_date": {"$gte": start_dt, "$lte": end_dt},
    }

    # 按需排序：先日期升序
    cursor = coll.find(filter_dict).sort("trade_date", ASCENDING)

    # 把 _id 去掉，方便后续直接 df = pd.DataFrame(list(records))
    records = [{k: v for k, v in doc.items() if k != "_id"} for doc in cursor]

    client.close()
    return records