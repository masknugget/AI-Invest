"""
查询推荐服务
基于 stock_qa 向量数据库，为用户输入推荐相似的问题和答案

Usage:
    from app.services.recommendation.recommend_query import QueryRecommendationService
    
    service = QueryRecommendationService()
    results = service.recommend("摩根大通股价", top_k=3)
    for r in results:
        print(f"Q: {r.query}")
        print(f"A: {r.answer}")
        print(f"Meta: {r.meta_data}")
        print(f"Score: {r.score:.3f}")
"""

import json
import logging
from typing import List, Optional
from pydantic import BaseModel
from dataclasses import dataclass

from tradingagents.searcher import VectorStore

logger = logging.getLogger("webapi")


# ==================== 数据模型 ====================

class QueryRecommendation(BaseModel):
    """查询推荐项"""
    uuid: str           # QA 对的唯一标识符
    query: str          # 相似的问题
    answer: str         # 对应答案
    meta_data: str      # 股票代码等元数据
    score: float        # 相似度分数 (0-1)


class RecommendQueryRequest(BaseModel):
    """查询推荐请求"""
    query: str
    top_k: int = 5


class RecommendQueryResponse(BaseModel):
    """查询推荐响应"""
    original_query: str
    recommendations: List[QueryRecommendation]
    total_found: int


def _extract_uuid(metadata: dict) -> str:
    """从 metadata 中提取 uuid
    
    优先顺序:
    1. metadata["uuid"]
    2. 解析 metadata["meta_data"] JSON 字符串中的 uuid
    3. 返回空字符串
    """
    # 1. 直接获取 uuid 字段
    uuid_val = metadata.get("uuid")
    if uuid_val:
        return str(uuid_val)
    
    # 2. 解析 meta_data JSON
    meta_data_str = metadata.get("meta_data", "")
    if meta_data_str and isinstance(meta_data_str, str):
        try:
            meta_dict = json.loads(meta_data_str)
            uuid_from_meta = meta_dict.get("uuid")
            if uuid_from_meta:
                return str(uuid_from_meta)
        except json.JSONDecodeError:
            pass
    
    return ""


# ==================== 核心服务类 ====================

class QueryRecommendationService:
    """
    查询推荐服务
    
    基于 stock_qa 向量集合，将用户 query 向量化后搜索相似问题，
    返回相关的问题-答案对作为推荐。
    """
    
    COLLECTION_NAME = "stock_qa"
    
    def __init__(self):
        """初始化，连接到 stock_qa 向量集合"""
        self.store = VectorStore(collection_name=self.COLLECTION_NAME)
        logger.info(f"✅ QueryRecommendationService 初始化: collection={self.COLLECTION_NAME}")
    
    def recommend(
        self,
        query: str,
        top_k: int = 5
    ) -> List[QueryRecommendation]:
        """
        推荐相似问题
        
        Args:
            query: 用户输入的查询文本
            top_k: 返回推荐数量，默认 5
            
        Returns:
            List[QueryRecommendation]: 推荐列表，按相似度降序
            
        Example:
            >>> service = QueryRecommendationService()
            >>> results = service.recommend("摩根大通现在多少钱？", top_k=3)
            >>> for r in results:
            ...     print(f"[{r.score:.3f}] {r.query}")
            ...     print(f"    → {r.answer[:50]}...")
        """
        if not query or not query.strip():
            return []
        
        try:
            # 向量搜索：在 stock_qa 集合中找相似的 query
            results = self.store.search(
                query=query,
                top_k=top_k
            )
            
            # 转换为 QueryRecommendation
            recommendations = []
            for r in results:
                rec = QueryRecommendation(
                    uuid=_extract_uuid(r.metadata),
                    query=r.content,           # content 是原始 query
                    answer=r.metadata.get("answer", ""),
                    meta_data=r.metadata.get("meta_data", ""),
                    score=r.score
                )
                recommendations.append(rec)
            
            logger.info(f"🔍 查询推荐: '{query[:30]}...' → {len(recommendations)} 条结果")
            return recommendations
            
        except Exception as e:
            logger.error(f"❌ 查询推荐失败: {e}")
            return []
    
    def recommend_with_details(
        self,
        query: str,
        top_k: int = 5
    ) -> RecommendQueryResponse:
        """
        推荐相似问题（完整响应格式）
        
        Args:
            query: 用户输入的查询文本
            top_k: 返回推荐数量
            
        Returns:
            RecommendQueryResponse: 包含原始 query 和推荐列表
        """
        recommendations = self.recommend(query, top_k)
        
        return RecommendQueryResponse(
            original_query=query,
            recommendations=recommendations,
            total_found=len(recommendations)
        )
    
    def get_collection_count(self) -> int:
        """获取 stock_qa 集合中的文档总数"""
        try:
            return self.store.count()
        except Exception as e:
            logger.error(f"❌ 获取文档数失败: {e}")
            return 0


# ==================== 便捷函数 ====================

_query_service_instance: Optional[QueryRecommendationService] = None


def get_query_recommendation_service() -> QueryRecommendationService:
    """
    获取查询推荐服务实例（单例）
    
    Returns:
        QueryRecommendationService: 服务实例
        
    Example:
        service = get_query_recommendation_service()
        results = service.recommend("股票开户", top_k=3)
    """
    global _query_service_instance
    
    if _query_service_instance is None:
        _query_service_instance = QueryRecommendationService()
    
    return _query_service_instance


# ==================== 直接使用示例 ====================

if __name__ == "__main__":
    print("=" * 60)
    print("查询推荐服务 - 使用示例")
    print("=" * 60)
    
    service = QueryRecommendationService()
    print(f"📊 stock_qa 集合文档数: {service.get_collection_count()}")
    print()
    
    # 示例 1：推荐相似问题
    test_queries = [
        "摩根大通股价多少",
        "苹果股票走势",
        "新手怎么开户",
        "茅台对标哪家公司",
    ]
    
    for user_query in test_queries:
        print(f"\n🔍 用户查询: '{user_query}'")
        print("-" * 50)
        
        results = service.recommend(user_query, top_k=3)
        
        if not results:
            print("   ⚠️  未找到相关推荐")
            continue
        
        for i, r in enumerate(results, 1):
            print(f"   {i}. [{r.score:.3f}] {r.query}")
            print(f"      答案: {r.answer[:60]}...")
            if r.meta_data:
                print(f"      股票: {r.meta_data}")
            print()
    
    print("\n✅ 示例完成")
