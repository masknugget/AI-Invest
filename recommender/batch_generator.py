"""
离线批处理生成器
每天运行一次，为所有股票生成LLM推荐数据
"""

import json
import logging
from typing import List, Dict, Any
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from pymongo import MongoClient

from tradingagents.llm_adapters.embeddings import create_dashscope_embeddings

from recommender.models import StockRecommendation
from recommender.stock_scanner import get_all_stocks

logger = logging.getLogger(__name__)

# MongoDB 配置
MONGO_URI = "mongodb://localhost:27017"
REC_DB = "recommendations"
REC_COLLECTION = "daily_stock_recommendations"


class BatchRecommendationGenerator:
    """每日推荐批量生成器"""
    
    # LLM 批次大小（控制API调用频率）
    BATCH_SIZE = 10
    
    def __init__(self):
        self.embeddings = create_dashscope_embeddings()
        self.client = MongoClient(MONGO_URI)
        self.db = self.client[REC_DB]
        self.collection = self.db[REC_COLLECTION]
        
        # 创建索引
        self.collection.create_index("symbol")
        self.collection.create_index("analysis_date")
        self.collection.create_index("overall_score")
        
        logger.info("BatchRecommendationGenerator 初始化完成")
    
    def generate_daily_recommendations(
        self,
        market: str = "cn",
        max_stocks: int = None
    ) -> Dict[str, Any]:
        """
        生成每日推荐数据
        
        Args:
            market: 市场
            max_stocks: 最大处理数量（测试用）
            
        Returns:
            统计信息
        """
        today = datetime.now().strftime("%Y-%m-%d")
        logger.info(f"开始生成 {today} 的推荐数据")
        
        # 1. 获取所有股票
        stocks = get_all_stocks(
            market=market,
            fields=["symbol", "name", "industry", "pe_ttm", "pb", "roe", "dv_ttm"]
        )
        
        if max_stocks:
            stocks = stocks[:max_stocks]
        
        total = len(stocks)
        logger.info(f"获取到 {total} 只股票")
        
        # 2. 分批调用LLM生成推荐（完成一个保存一个）
        processed = 0
        saved_count = 0
        
        for i in range(0, total, self.BATCH_SIZE):
            batch = stocks[i:i + self.BATCH_SIZE]
            
            try:
                batch_recs = self._process_batch(batch, today)
                processed += len(batch)
                
                # 立即保存该批次结果
                if batch_recs:
                    self._save_batch_to_mongodb(batch_recs, today)
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
    
    def _process_batch(
        self,
        stocks: List[Dict],
        analysis_date: str
    ) -> List[StockRecommendation]:
        """处理一批股票"""
        
        # 构建提示词
        prompt = self._build_batch_prompt(stocks)
        
        # 调用LLM
        response = self._call_llm(prompt)
        
        # 解析结果
        recommendations = self._parse_response(stocks, response, analysis_date)
        
        return recommendations
    
    def _build_batch_prompt(self, stocks: List[Dict]) -> str:
        """构建批量分析提示词"""
        
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
5. 针对不同风格的推荐理由 (各30字以内)

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
            "reason_for_value": "低估值，适合价值投资者",
            "reason_for_growth": "成长性一般",
            "reason_for_dividend": "股息率4%，稳定分红"
        }}
    ]
}}

注意:
1. 必须为每只股票生成分析结果
2. suitable_for 必须是列表，可包含多个风格
3. 推荐理由要简洁具体
"""
        return prompt
    
    def _call_llm(self, prompt: str) -> str:
        """调用LLM"""
        from openai import OpenAI
        
        client = OpenAI(
            api_key=self.embeddings.client.api_key,
            base_url=self.embeddings.client.base_url
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
    
    def _parse_response(
        self,
        stocks: List[Dict],
        response: str,
        analysis_date: str
    ) -> List[StockRecommendation]:
        """解析LLM响应"""
        try:
            # 提取JSON
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]
            
            data = json.loads(json_str.strip())
            
            # 建立symbol到原始数据的映射
            stock_map = {s.get("symbol"): s for s in stocks}
            
            recommendations = []
            for item in data.get("results", []):
                symbol = item["symbol"]
                stock = stock_map.get(symbol, {})
                
                rec = StockRecommendation(
                    symbol=symbol,
                    name=stock.get("name", ""),
                    industry=stock.get("industry", ""),
                    pe=self._to_float(stock.get("pe_ttm")),
                    pb=self._to_float(stock.get("pb")),
                    roe=self._to_float(stock.get("roe")),
                    dividend_yield=self._to_float(stock.get("dv_ttm")),
                    overall_score=float(item.get("overall_score", 50)),
                    recommendation=item.get("recommendation", "持有"),
                    risk_level=item.get("risk_level", "中"),
                    suitable_for=item.get("suitable_for", []),
                    reason_for_value=item.get("reason_for_value", ""),
                    reason_for_growth=item.get("reason_for_growth", ""),
                    reason_for_dividend=item.get("reason_for_dividend", ""),
                    analysis_date=analysis_date,
                )
                recommendations.append(rec)
            
            return recommendations
            
        except Exception as e:
            logger.error(f"解析响应失败: {e}\n响应: {response}")
            return []
    
    def _save_batch_to_mongodb(
        self,
        recommendations: List[StockRecommendation],
        analysis_date: str
    ):
        """保存单个批次到MongoDB（增量保存）"""
        docs = []
        for rec in recommendations:
            doc = rec.to_dict()
            doc["analysis_date"] = analysis_date
            doc["updated_at"] = datetime.now()
            docs.append(doc)
        
        if docs:
            # 使用 upsert 避免重复（基于 symbol + analysis_date）
            for doc in docs:
                self.collection.update_one(
                    {"symbol": doc["symbol"], "analysis_date": analysis_date},
                    {"$set": doc},
                    upsert=True
                )
            logger.info(f"保存 {len(docs)} 条推荐数据到MongoDB")
    
    def _save_to_mongodb(
        self,
        recommendations: List[StockRecommendation],
        analysis_date: str
    ):
        """保存到MongoDB（全量替换，用于兼容性）"""
        # 删除旧数据
        self.collection.delete_many({"analysis_date": analysis_date})
        
        # 插入新数据
        docs = []
        for rec in recommendations:
            doc = rec.to_dict()
            doc["analysis_date"] = analysis_date
            doc["updated_at"] = datetime.now()
            docs.append(doc)
        
        if docs:
            self.collection.insert_many(docs)
            logger.info(f"保存 {len(docs)} 条推荐数据到MongoDB")
    
    @staticmethod
    def _to_float(value) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except:
            return None


# 便捷函数
def run_daily_batch(market: str = "cn", max_stocks: int = None):
    """运行每日批处理"""
    generator = BatchRecommendationGenerator()
    return generator.generate_daily_recommendations(market, max_stocks)


if __name__ == "__main__":
    # 测试运行
    result = run_daily_batch(max_stocks=20)
    print(f"批处理结果: {result}")
