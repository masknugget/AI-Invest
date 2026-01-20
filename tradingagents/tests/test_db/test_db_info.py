from pymongo import MongoClient
from pymongo.collection import Collection
from tradingagents.db.document import MONGO_URI, detect_market

symbol = '000001.SZ'
market = detect_market(symbol)
clean_symbol = symbol.split('.')[0] if '.' in symbol else symbol

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

    if info:
        result = {
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
