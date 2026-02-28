"""
股票遍历查询模块 - 用于批量获取和处理股票信息

功能：
1. 获取所有股票列表
2. 批量遍历查询股票基本信息
3. 支持市场筛选、行业筛选
4. 支持分页/分批处理
5. 支持并发查询优化性能
"""

from datetime import datetime
from typing import List, Dict, Any, Optional, Iterator, Callable, Union
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database
import concurrent.futures
from functools import lru_cache

# -------------------- 配置 --------------------
MONGO_URI = "mongodb://localhost:27017"
DEFAULT_BATCH_SIZE = 100  # 默认每批处理的股票数量
MAX_WORKERS = 4  # 默认并发线程数


# ==================== 核心工具函数 ====================

def _init_db(db_name: str = "stock_db") -> tuple[MongoClient, Database]:
    """
    初始化 MongoDB 连接
    
    Args:
        db_name: 数据库名称，默认为 'stock_db'
        
    Returns:
        tuple: (client, db) - MongoClient 实例和 Database 实例
    """
    client = MongoClient(MONGO_URI)
    db = client[db_name]
    return client, db


# ==================== 股票列表获取 ====================

def get_all_stocks(
    market: Optional[str] = None,
    industry: Optional[str] = None,
    fields: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    获取所有股票基本信息列表
    
    Args:
        market: 市场筛选，可选 'cn'(A股), 'hk'(港股), 'us'(美股)
        industry: 行业筛选，如 '银行', '科技' 等
        fields: 指定返回的字段列表，None 返回所有字段
        
    Returns:
        List[Dict]: 股票基本信息列表
        
    Example:
        >>> # 获取所有A股
        >>> cn_stocks = get_all_stocks(market='cn')
        >>> 
        >>> # 获取所有科技行业股票
        >>> tech_stocks = get_all_stocks(industry='科技')
        >>> 
        >>> # 只获取股票代码和名称
        >>> symbols = get_all_stocks(fields=['symbol', 'name'])
    """
    client, db = _init_db()
    try:
        coll: Collection = db["stock_daily_basic"]
        
        # 构建查询条件
        filter_dict = {}
        if market:
            filter_dict["market"] = market
        if industry:
            filter_dict["industry"] = {"$regex": industry, "$options": "i"}
        
        # 构建投影（指定返回字段）
        projection = {"_id": 0}
        if fields:
            for field in fields:
                projection[field] = 1
        
        cursor = coll.find(filter_dict, projection)
        return list(cursor)
    finally:
        client.close()


def get_all_symbols(market: Optional[str] = None) -> List[str]:
    """
    获取所有股票代码列表（轻量级查询）
    
    Args:
        market: 市场筛选，可选 'cn', 'hk', 'us'
        
    Returns:
        List[str]: 股票代码列表
    """
    client, db = _init_db()
    try:
        coll: Collection = db["stock_daily_basic"]
        
        filter_dict = {}
        if market:
            filter_dict["market"] = market
        
        cursor = coll.find(filter_dict, {"symbol": 1, "_id": 0})
        return [doc["symbol"] for doc in cursor if "symbol" in doc]
    finally:
        client.close()


def get_stock_count(market: Optional[str] = None) -> int:
    """
    获取股票总数
    
    Args:
        market: 市场筛选
        
    Returns:
        int: 股票数量
    """
    client, db = _init_db()
    try:
        coll: Collection = db["stock_daily_basic"]
        
        filter_dict = {}
        if market:
            filter_dict["market"] = market
        
        return coll.count_documents(filter_dict)
    finally:
        client.close()


# ==================== 批量遍历查询 ====================

def iterate_stocks(
    market: Optional[str] = None,
    industry: Optional[str] = None,
    fields: Optional[List[str]] = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    sort_by: str = "symbol",
    sort_order: int = ASCENDING
) -> Iterator[List[Dict[str, Any]]]:
    """
    分批遍历股票（生成器，内存友好）
    
    Args:
        market: 市场筛选
        industry: 行业筛选
        fields: 指定返回字段
        batch_size: 每批返回的股票数量
        sort_by: 排序字段
        sort_order: 排序方式（ASCENDING 或 DESCENDING）
        
    Yields:
        List[Dict]: 每批股票信息列表
        
    Example:
        >>> # 分批处理所有A股
        >>> for batch in iterate_stocks(market='cn', batch_size=50):
        ...     for stock in batch:
        ...         print(f"处理: {stock['symbol']} - {stock['name']}")
        ...     # 每处理完一批可以保存进度或释放资源
    """
    client, db = _init_db()
    try:
        coll: Collection = db["stock_daily_basic"]
        
        # 构建查询条件
        filter_dict = {}
        if market:
            filter_dict["market"] = market
        if industry:
            filter_dict["industry"] = {"$regex": industry, "$options": "i"}
        
        # 构建投影
        projection = {"_id": 0}
        if fields:
            for field in fields:
                projection[field] = 1
        
        # 使用 skip/limit 分页
        skip = 0
        while True:
            cursor = (coll
                     .find(filter_dict, projection)
                     .sort(sort_by, sort_order)
                     .skip(skip)
                     .limit(batch_size))
            
            batch = list(cursor)
            if not batch:
                break
            
            yield batch
            skip += batch_size
            
    finally:
        client.close()


def iterate_stocks_with_cursor(
    market: Optional[str] = None,
    industry: Optional[str] = None,
    fields: Optional[List[str]] = None,
    sort_by: str = "symbol",
    sort_order: int = ASCENDING
) -> Iterator[Dict[str, Any]]:
    """
    逐个遍历股票（游标方式，最省内存）
    
    Args:
        market: 市场筛选
        industry: 行业筛选
        fields: 指定返回字段
        sort_by: 排序字段
        sort_order: 排序方式
        
    Yields:
        Dict: 单个股票信息
        
    Example:
        >>> # 逐个处理所有股票
        >>> for stock in iterate_stocks_with_cursor(market='hk'):
        ...     process_stock(stock)
    """
    client, db = _init_db()
    try:
        coll: Collection = db["stock_daily_basic"]
        
        filter_dict = {}
        if market:
            filter_dict["market"] = market
        if industry:
            filter_dict["industry"] = {"$regex": industry, "$options": "i"}
        
        projection = {"_id": 0}
        if fields:
            for field in fields:
                projection[field] = 1
        
        cursor = coll.find(filter_dict, projection).sort(sort_by, sort_order)
        
        for doc in cursor:
            yield doc
            
    finally:
        client.close()


# ==================== 批量数据获取 ====================

def get_stocks_daily_data(
    symbols: List[str],
    start_date: str,
    end_date: str,
    data_type: str = "technical"
) -> Dict[str, List[Dict[str, Any]]]:
    """
    批量获取多只股票的历史数据
    
    Args:
        symbols: 股票代码列表
        start_date: 开始日期，格式：YYYY-MM-DD
        end_date: 结束日期，格式：YYYY-MM-DD
        data_type: 数据类型，'technical' 或 'basic'
        
    Returns:
        Dict: {symbol: [data_list]}
        
    Example:
        >>> symbols = ['000001', '000002', '600000']
        >>> data = get_stocks_daily_data(symbols, '2024-01-01', '2024-12-31')
        >>> print(data['000001'])  # 获取平安银行的数据
    """
    from datetime import datetime
    
    client, db = _init_db()
    try:
        collection_name = f"stock_daily_{data_type}"
        coll: Collection = db[collection_name]
        
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        filter_dict = {
            "symbol": {"$in": symbols},
            "trade_date": {"$gte": start_dt, "$lte": end_dt},
        }
        
        cursor = coll.find(filter_dict, {"_id": 0}).sort("trade_date", ASCENDING)
        
        # 按 symbol 分组
        result: Dict[str, List[Dict]] = {symbol: [] for symbol in symbols}
        for doc in cursor:
            symbol = doc.get("symbol")
            if symbol in result:
                result[symbol].append(doc)
        
        return result
    finally:
        client.close()


def batch_process_stocks(
    processor: Callable[[Dict[str, Any]], Any],
    market: Optional[str] = None,
    industry: Optional[str] = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_workers: int = MAX_WORKERS
) -> List[Any]:
    """
    并发批量处理股票
    
    Args:
        processor: 处理函数，接收股票信息字典，返回处理结果
        market: 市场筛选
        industry: 行业筛选
        batch_size: 每批处理数量
        max_workers: 并发线程数
        
    Returns:
        List[Any]: 所有处理结果
        
    Example:
        >>> def my_processor(stock):
        ...     # 对每只股票进行处理
        ...     return analyze_stock(stock['symbol'])
        >>> 
        >>> results = batch_process_stocks(my_processor, market='cn', max_workers=4)
    """
    results = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        for batch in iterate_stocks(market, industry, batch_size=batch_size):
            futures = [executor.submit(processor, stock) for stock in batch]
            batch_results = [f.result() for f in concurrent.futures.as_completed(futures)]
            results.extend(batch_results)
    
    return results


# ==================== 统计与筛选 ====================

def get_market_distribution() -> Dict[str, int]:
    """
    获取各市场的股票数量分布
    
    Returns:
        Dict: {market: count}
        
    Example:
        >>> distribution = get_market_distribution()
        >>> print(f"A股: {distribution.get('cn', 0)} 只")
        >>> print(f"港股: {distribution.get('hk', 0)} 只")
        >>> print(f"美股: {distribution.get('us', 0)} 只")
    """
    client, db = _init_db()
    try:
        coll: Collection = db["stock_daily_basic"]
        
        pipeline = [
            {"$group": {"_id": "$market", "count": {"$sum": 1}}}
        ]
        
        result = {}
        for doc in coll.aggregate(pipeline):
            market = doc.get("_id", "unknown")
            result[market] = doc.get("count", 0)
        
        return result
    finally:
        client.close()


def get_industries(market: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    获取所有行业列表及股票数量
    
    Args:
        market: 市场筛选
        
    Returns:
        List[Dict]: [{"industry": "银行", "count": 42}, ...]
    """
    client, db = _init_db()
    try:
        coll: Collection = db["stock_daily_basic"]
        
        match_stage = {}
        if market:
            match_stage["market"] = market
        
        pipeline = []
        if match_stage:
            pipeline.append({"$match": match_stage})
        
        pipeline.extend([
            {"$group": {"_id": "$industry", "count": {"$sum": 1}}},
            {"$sort": {"count": DESCENDING}}
        ])
        
        cursor = coll.aggregate(pipeline)
        return [{"industry": doc.get("_id", "未知"), "count": doc.get("count", 0)} for doc in cursor]
    finally:
        client.close()


def filter_stocks(
    market: Optional[str] = None,
    industries: Optional[List[str]] = None,
    min_market_cap: Optional[float] = None,
    max_market_cap: Optional[float] = None,
    fields: Optional[List[str]] = None,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    多条件筛选股票
    
    Args:
        market: 市场筛选
        industries: 行业列表
        min_market_cap: 最小市值
        max_market_cap: 最大市值
        fields: 返回字段
        limit: 返回数量限制
        
    Returns:
        List[Dict]: 符合条件的股票列表
    """
    client, db = _init_db()
    try:
        coll: Collection = db["stock_daily_basic"]
        
        # 构建查询条件
        filter_dict = {}
        
        if market:
            filter_dict["market"] = market
        
        if industries:
            filter_dict["industry"] = {"$in": industries}
        
        if min_market_cap is not None or max_market_cap is not None:
            market_cap_filter = {}
            if min_market_cap is not None:
                market_cap_filter["$gte"] = min_market_cap
            if max_market_cap is not None:
                market_cap_filter["$lte"] = max_market_cap
            filter_dict["total_mv"] = market_cap_filter
        
        # 构建投影
        projection = {"_id": 0}
        if fields:
            for field in fields:
                projection[field] = 1
        
        cursor = coll.find(filter_dict, projection)
        
        if limit:
            cursor = cursor.limit(limit)
        
        return list(cursor)
    finally:
        client.close()


# ==================== 实用工具 ====================

@lru_cache(maxsize=128)
def get_stock_basic_cached(symbol: str) -> Optional[Dict[str, Any]]:
    """
    获取股票基本信息（带缓存）
    
    Args:
        symbol: 股票代码
        
    Returns:
        Dict: 股票基本信息
    """
    client, db = _init_db()
    try:
        coll: Collection = db["stock_daily_basic"]
        return coll.find_one({"symbol": symbol}, {"_id": 0})
    finally:
        client.close()


def clear_cache():
    """清除股票信息缓存"""
    get_stock_basic_cached.cache_clear()


# ==================== 使用示例 ====================

if __name__ == "__main__":
    # 示例1: 获取所有A股股票代码
    print("=== A股股票列表 ===")
    cn_symbols = get_all_symbols(market='cn')
    print(f"A股总数: {len(cn_symbols)}")
    print(f"前5只: {cn_symbols[:5]}")
    
    # 示例2: 分批遍历处理
    print("\n=== 分批遍历港股 ===")
    for i, batch in enumerate(iterate_stocks(market='hk', batch_size=10)):
        print(f"第{i+1}批: {[s['symbol'] for s in batch[:3]]}...")
        if i >= 2:  # 只演示前3批
            break
    
    # 示例3: 获取市场分布
    print("\n=== 市场分布 ===")
    distribution = get_market_distribution()
    for market, count in distribution.items():
        print(f"  {market}: {count} 只")
    
    # 示例4: 获取行业分布
    print("\n=== 行业分布 (前5) ===")
    industries = get_industries()
    for ind in industries[:5]:
        print(f"  {ind['industry']}: {ind['count']} 只")
