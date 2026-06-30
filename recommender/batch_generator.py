"""
离线批处理生成器
每天运行一次，为所有股票生成LLM推荐数据
函数式风格实现
"""

import json
import logging
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from functools import partial

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database



from recommender.models import StockRecommendation
from recommender.stock_scanner import get_all_symbols
from tradingagents.llm_adapters.embeddings import create_embeddings

logger = logging.getLogger(__name__)

# MongoDB 配置
MONGO_URI = "mongodb://localhost:27017"
REC_DB = "recommendations"
REC_COLLECTION = "daily_stock_recommendations"

# 默认批次大小
DEFAULT_BATCH_SIZE = 10


# ==================== 股票查询函数 ====================

def get_stocks_by_symbols(symbols: List[str]) -> List[Dict[str, Any]]:
    """
    根据股票代码列表查询详细信息
    
    Args:
        symbols: 股票代码列表
        
    Returns:
        股票详细信息列表
    """
    from recommender.stock_scanner import _init_db
    
    if not symbols:
        return []
    
    client, db = _init_db()
    try:
        coll = db["stock_daily_basic"]
        
        # 查询指定字段
        projection = {
            "_id": 0,
            "symbol": 1,
            "name": 1,
            "industry": 1,
            "pe_ttm": 1,
            "pb": 1,
            "roe": 1,
            "dv_ttm": 1
        }
        
        cursor = coll.find({"symbol": {"$in": symbols}}, projection)
        stocks = list(cursor)
        
        logger.info(f"查询到 {len(stocks)} 只股票的详细信息")
        return stocks
        
    finally:
        client.close()


# ==================== 初始化函数 ====================

def init_mongodb(uri: str = MONGO_URI, db_name: str = REC_DB) -> tuple[MongoClient, Database, Collection]:
    """
    初始化 MongoDB 连接
    
    Args:
        uri: MongoDB 连接 URI
        db_name: 数据库名称
        
    Returns:
        tuple: (client, db, collection)
    """
    client = MongoClient(uri)
    db = client[db_name]
    collection = db[REC_COLLECTION]
    
    # 创建索引
    collection.create_index("symbol")
    collection.create_index("analysis_date")
    collection.create_index("overall_score")
    
    return client, db, collection


def init_embeddings():
    """初始化嵌入模型"""
    return create_embeddings()


# ==================== 核心处理函数 ====================

def generate_daily_recommendations(
    max_stocks: int = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    collection: Collection = None,
    embeddings = None
) -> Dict[str, Any]:
    """
    生成每日推荐数据
    
    Args:
        max_stocks: 最大处理数量（测试用）
        batch_size: LLM 批次大小
        collection: MongoDB 集合（可选，默认新建连接）
        embeddings: 嵌入模型实例（可选，默认新建）
        
    Returns:
        统计信息
    """
    # 初始化依赖
    client = None
    if collection is None:
        client, _, collection = init_mongodb()
    
    if embeddings is None:
        embeddings = init_embeddings()
    
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        logger.info(f"开始生成 {today} 的推荐数据")
        
        # 1. 获取所有股票代码，然后查询详细信息
        symbols = get_all_symbols()
        
        if max_stocks:
            symbols = symbols[:max_stocks]
        
        # 查询个股详细信息
        stocks = get_stocks_by_symbols(symbols)
        
        if not stocks:
            logger.warning("未获取到任何股票信息")
            return {
                "date": today,
                "total_stocks": 0,
                "processed": 0,
                "status": "no_data"
            }
        
        total = len(stocks)
        logger.info(f"获取到 {total} 只股票")
        
        # 2. 分批调用LLM生成推荐（完成一个保存一个）
        processed = 0
        saved_count = 0
        
        for i in range(0, total, batch_size):
            batch = stocks[i:i + batch_size]
            
            try:
                batch_recs = process_batch(batch, today, embeddings)
                processed += len(batch)
                
                # 立即保存该批次结果
                if batch_recs:
                    save_batch_to_mongodb(batch_recs, today, collection)
                    saved_count += len(batch_recs)
                    logger.info(f"批次完成并保存: {len(batch_recs)} 条")
                
                logger.info(f"进度: {processed}/{total}")
                
            except Exception as e:
                logger.error(f"处理批次失败: {e}")
                continue
        
        result = {
            "date": today,
            "total_stocks": total,
            "processed": saved_count,
            "status": "success"
        }
        
        logger.info(f"生成完成: {result}")
        return result
        
    finally:
        if client:
            client.close()


def process_batch(
    stocks: List[Dict],
    analysis_date: str,
    embeddings
) -> List[StockRecommendation]:
    """
    处理一批股票
    
    Args:
        stocks: 股票列表
        analysis_date: 分析日期
        embeddings: 嵌入模型实例
        
    Returns:
        推荐列表
    """
    # 构建提示词
    prompt = build_batch_prompt(stocks)
    
    # 调用LLM
    response = call_llm(prompt, embeddings)
    
    # 解析结果
    recommendations = parse_response(stocks, response, analysis_date)
    
    return recommendations


# ==================== 提示词构建 ====================

def build_batch_prompt(stocks: List[Dict]) -> str:
    """
    构建批量分析提示词
    
    Args:
        stocks: 股票列表
        
    Returns:
        提示词字符串
    """
    stocks_text = "\n".join([
        f"{i+1}. {s.get('name')}({s.get('symbol')}) - {s.get('industry', '未知行业')} "
        f"PE:{s.get('pe_ttm', 'N/A')} PB:{s.get('pb', 'N/A')} "
        f"ROE:{s.get('roe', 'N/A')}% 股息:{s.get('dv_ttm', 'N/A')}%"
        for i, s in enumerate(stocks)
    ])
    
    prompt = f"""作为专业投资分析师，请对以下股票进行批量分析。

需要分析的维度：
1. 综合评分 (0-100)
2. 推荐等级 (强烈买入/买入/持有/卖出)
3. 风险等级 (低/中/高)
4. 适合的投资风格 (价值投资/成长投资/股息投资/趋势投资，可多选)
5. 通用推荐理由 (50字以内，简明扼要说明为什么值得关注)
6. 针对不同风格的推荐理由 (各30字以内)

股票列表:
{stocks_text}

请严格按照以下JSON格式输出，包含所有股票的分析结果:
{{
    "results": [
        {{
            "symbol": "股票代码",
            "overall_score": 85,
            "recommendation": "买入",
            "risk_level": "中",
            "suitable_for": ["价值投资", "股息投资"],
            "reason": "低估值高股息，基本面稳健，适合中长期持有",
            "reason_for_value": "低估值，适合价值投资者",
            "reason_for_growth": "成长性一般",
            "reason_for_dividend": "股息率4%，稳定分红"
        }}
    ]
}}

注意:
1. 必须为每只股票生成分析结果
2. suitable_for 必须是列表，可包含多个风格
3. reason 字段必须生成，这是给用户展示的核心推荐理由（50字以内）
4. 针对不同风格的推荐理由要简洁具体，帮助用户快速决策
"""
    return prompt


# ==================== LLM 调用 ====================

def call_llm(prompt: str, embeddings) -> str:
    """
    调用LLM
    
    Args:
        prompt: 提示词
        embeddings: 嵌入模型实例
        
    Returns:
        LLM 响应内容
    """
    from openai import OpenAI
    
    client = OpenAI(
        api_key=embeddings.client.api_key,
        base_url=embeddings.client.base_url
    )
    
    response = client.chat.completions.create(
        model="qwen-turbo",
        messages=[
            {"role": "system", "content": "你是专业的股票分析师，擅长批量分析股票并给出投资建议。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=2000
    )
    
    return response.choices[0].message.content


# ==================== 响应解析 ====================

def parse_response(
    stocks: List[Dict],
    response: str,
    analysis_date: str
) -> List[StockRecommendation]:
    """
    解析LLM响应
    
    Args:
        stocks: 原始股票列表
        response: LLM 响应
        analysis_date: 分析日期
        
    Returns:
        推荐列表
    """
    try:
        # 提取JSON
        json_str = extract_json_from_response(response)
        data = json.loads(json_str)
        
        # 建立symbol到原始数据的映射
        stock_map = {s.get("symbol"): s for s in stocks}
        
        recommendations = []
        for item in data.get("results", []):
            symbol = item["symbol"]
            stock = stock_map.get(symbol, {})
            
            rec = create_recommendation(item, stock, analysis_date)
            recommendations.append(rec)
        
        return recommendations
        
    except Exception as e:
        logger.error(f"解析响应失败: {e}\n响应: {response}")
        return []


def extract_json_from_response(response: str) -> str:
    """
    从响应中提取 JSON 字符串
    
    Args:
        response: 原始响应
        
    Returns:
        JSON 字符串
    """
    if "```json" in response:
        return response.split("```json")[1].split("```")[0]
    elif "```" in response:
        return response.split("```")[1].split("```")[0]
    return response


def create_recommendation(
    item: Dict,
    stock: Dict,
    analysis_date: str
) -> StockRecommendation:
    """
    创建推荐对象
    
    Args:
        item: LLM 解析结果
        stock: 原始股票数据
        analysis_date: 分析日期
        
    Returns:
        StockRecommendation 对象
    """
    return StockRecommendation(
        symbol=item["symbol"],
        name=stock.get("name", ""),
        industry=stock.get("industry", ""),
        pe=to_float(stock.get("pe_ttm")),
        pb=to_float(stock.get("pb")),
        roe=to_float(stock.get("roe")),
        dividend_yield=to_float(stock.get("dv_ttm")),
        overall_score=float(item.get("overall_score", 50)),
        recommendation=item.get("recommendation", "持有"),
        risk_level=item.get("risk_level", "中"),
        suitable_for=item.get("suitable_for", []),
        reason=item.get("reason", ""),
        reason_for_value=item.get("reason_for_value", ""),
        reason_for_growth=item.get("reason_for_growth", ""),
        reason_for_dividend=item.get("reason_for_dividend", ""),
        analysis_date=analysis_date,
    )


# ==================== 数据保存 ====================

def save_batch_to_mongodb(
    recommendations: List[StockRecommendation],
    analysis_date: str,
    collection: Collection
):
    """
    保存单个批次到MongoDB（增量保存）
    
    Args:
        recommendations: 推荐列表
        analysis_date: 分析日期
        collection: MongoDB 集合
    """
    docs = recommendations_to_docs(recommendations, analysis_date)
    
    if docs:
        # 使用 upsert 避免重复（基于 symbol + analysis_date）
        for doc in docs:
            collection.update_one(
                {"symbol": doc["symbol"], "analysis_date": analysis_date},
                {"$set": doc},
                upsert=True
            )
        logger.info(f"保存 {len(docs)} 条推荐数据到MongoDB")


def save_to_mongodb(
    recommendations: List[StockRecommendation],
    analysis_date: str,
    collection: Collection
):
    """
    保存到MongoDB（全量替换，用于兼容性）
    
    Args:
        recommendations: 推荐列表
        analysis_date: 分析日期
        collection: MongoDB 集合
    """
    # 删除旧数据
    collection.delete_many({"analysis_date": analysis_date})
    
    # 插入新数据
    docs = recommendations_to_docs(recommendations, analysis_date)
    
    if docs:
        collection.insert_many(docs)
        logger.info(f"保存 {len(docs)} 条推荐数据到MongoDB")


def recommendations_to_docs(
    recommendations: List[StockRecommendation],
    analysis_date: str
) -> List[Dict]:
    """
    将推荐对象列表转换为文档列表
    
    Args:
        recommendations: 推荐列表
        analysis_date: 分析日期
        
    Returns:
        文档列表
    """
    docs = []
    for rec in recommendations:
        doc = rec.to_dict()
        doc["analysis_date"] = analysis_date
        doc["updated_at"] = datetime.now()
        docs.append(doc)
    return docs


# ==================== 工具函数 ====================

def to_float(value) -> Optional[float]:
    """将值转换为浮点数"""
    if value is None:
        return None
    try:
        return float(value)
    except:
        return None


# ==================== 便捷入口函数 ====================

def run_daily_batch(max_stocks: int = None) -> Dict[str, Any]:
    """
    运行每日批处理
    
    Args:
        max_stocks: 最大处理数量
        
    Returns:
        统计信息
    """
    return generate_daily_recommendations(
        max_stocks=max_stocks
    )


# ==================== 高级批量处理 ====================

def batch_process_with_concurrency(
    stocks: List[Dict],
    processor: Callable[[List[Dict], str], List[StockRecommendation]],
    analysis_date: str,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_workers: int = 4
) -> List[StockRecommendation]:
    """
    并发批量处理股票
    
    Args:
        stocks: 股票列表
        processor: 处理函数
        analysis_date: 分析日期
        batch_size: 批次大小
        max_workers: 最大并发数
        
    Returns:
        所有推荐结果
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    # 分批
    batches = [stocks[i:i + batch_size] for i in range(0, len(stocks), batch_size)]
    
    all_recommendations = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_batch = {
            executor.submit(processor, batch, analysis_date): batch 
            for batch in batches
        }
        
        # 收集结果
        for future in as_completed(future_to_batch):
            try:
                batch_recs = future.result()
                all_recommendations.extend(batch_recs)
            except Exception as e:
                batch = future_to_batch[future]
                symbols = [s.get("symbol") for s in batch]
                logger.error(f"处理批次失败 {symbols}: {e}")
    
    return all_recommendations


if __name__ == "__main__":
    # 测试运行
    result = run_daily_batch(max_stocks=20)
    print(f"批处理结果: {result}")
