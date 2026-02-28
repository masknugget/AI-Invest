"""
向量搜索服务
提供股票和文档的语义搜索功能
"""

import logging
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime

from tradingagents.searcher import VectorStore

logger = logging.getLogger("webapi")


# ==================== 简单模型定义 ====================

class SearchRequest(BaseModel):
    """搜索请求"""
    query: str
    top_k: int = 5
    filter_metadata: Optional[Dict[str, Any]] = None


class SearchResult(BaseModel):
    """搜索结果"""
    id: str
    content: str
    score: float
    metadata: Dict[str, Any]


class DocumentInsert(BaseModel):
    """文档插入请求"""
    content: str
    metadata: Optional[Dict[str, Any]] = None
    doc_id: Optional[str] = None


class DocumentInsertResponse(BaseModel):
    """文档插入响应"""
    doc_id: str
    content_preview: str
    status: str


class SearchStats(BaseModel):
    """搜索统计"""
    collection_name: str
    total_documents: int
    last_updated: Optional[str] = None


# ==================== 核心服务类 ====================

class SearchService:
    """
    向量搜索服务
    包装 VectorStore，提供业务层接口
    """
    
    DEFAULT_COLLECTION = "stock_basic"
    
    def __init__(self, collection_name: str = None):
        """
        初始化搜索服务
        
        Args:
            collection_name: 集合名称，默认使用 stock_basic
        """
        self.collection_name = collection_name or self.DEFAULT_COLLECTION
        self.store = VectorStore(collection_name=self.collection_name)
        logger.info(f"✅ SearchService 初始化: collection={self.collection_name}")
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        语义搜索
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            filter_metadata: 元数据过滤条件
            
        Returns:
            List[SearchResult]: 搜索结果列表
        """
        try:
            results = self.store.search(
                query=query,
                top_k=top_k,
                filter_metadata=filter_metadata
            )
            
            # 转换为 SearchResult 模型
            return [
                SearchResult(
                    id=r.id,
                    content=r.content,
                    score=r.score,
                    metadata=r.metadata
                )
                for r in results
            ]
        except Exception as e:
            logger.error(f"❌ 搜索失败: {e}")
            return []
    
    def add_document(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        doc_id: Optional[str] = None
    ) -> str:
        """
        添加单条文档
        
        Args:
            content: 文档内容
            metadata: 元数据
            doc_id: 文档ID（可选）
            
        Returns:
            str: 文档ID
        """
        try:
            # 添加时间戳
            meta = metadata or {}
            meta["created_at"] = datetime.now().isoformat()
            meta["source"] = meta.get("source", "api")
            
            doc_id = self.store.insert(
                content=content,
                metadata=meta,
                doc_id=doc_id
            )
            
            logger.info(f"✅ 添加文档: {doc_id}")
            return doc_id
        except Exception as e:
            logger.error(f"❌ 添加文档失败: {e}")
            raise
    
    def add_documents(self, documents: List[DocumentInsert]) -> List[str]:
        """
        批量添加文档
        
        Args:
            documents: 文档列表
            
        Returns:
            List[str]: 文档ID列表
        """
        try:
            # 转换为 VectorStore 格式
            docs_for_store = []
            for doc in documents:
                meta = doc.metadata or {}
                meta["created_at"] = datetime.now().isoformat()
                meta["source"] = meta.get("source", "api")
                
                docs_for_store.append({
                    "id": doc.doc_id,
                    "content": doc.content,
                    "metadata": meta
                })
            
            doc_ids = self.store.add_documents(docs_for_store)
            logger.info(f"✅ 批量添加文档: {len(doc_ids)} 条")
            return doc_ids
        except Exception as e:
            logger.error(f"❌ 批量添加文档失败: {e}")
            raise
    
    def delete_document(self, doc_id: str) -> bool:
        """
        删除文档
        
        Args:
            doc_id: 文档ID
            
        Returns:
            bool: 是否成功
        """
        try:
            result = self.store.delete(doc_id)
            if result:
                logger.info(f"✅ 删除文档: {doc_id}")
            else:
                logger.warning(f"⚠️ 删除文档失败: {doc_id}")
            return result
        except Exception as e:
            logger.error(f"❌ 删除文档异常: {e}")
            return False
    
    def get_document(self, doc_id: str) -> Optional[SearchResult]:
        """
        获取单个文档
        
        Args:
            doc_id: 文档ID
            
        Returns:
            SearchResult: 文档信息
        """
        try:
            result = self.store.get(doc_id)
            if result:
                return SearchResult(
                    id=result.id,
                    content=result.content,
                    score=result.score,
                    metadata=result.metadata
                )
            return None
        except Exception as e:
            logger.error(f"❌ 获取文档失败: {e}")
            return None
    
    def get_stats(self) -> SearchStats:
        """
        获取统计信息
        
        Returns:
            SearchStats: 统计数据
        """
        try:
            count = self.store.count()
            return SearchStats(
                collection_name=self.collection_name,
                total_documents=count,
                last_updated=datetime.now().isoformat()
            )
        except Exception as e:
            logger.error(f"❌ 获取统计失败: {e}")
            return SearchStats(
                collection_name=self.collection_name,
                total_documents=0,
                last_updated=None
            )
    
    def list_documents(self, limit: int = 100) -> List[SearchResult]:
        """
        列出所有文档
        
        Args:
            limit: 数量限制
            
        Returns:
            List[SearchResult]: 文档列表
        """
        try:
            results = self.store.list_all(limit=limit)
            return [
                SearchResult(
                    id=r.id,
                    content=r.content,
                    score=r.score,
                    metadata=r.metadata
                )
                for r in results
            ]
        except Exception as e:
            logger.error(f"❌ 列出文档失败: {e}")
            return []


# ==================== 便捷函数 ====================

_search_service_instance: Optional[SearchService] = None


def get_search_service(collection_name: str = None) -> SearchService:
    """
    获取搜索服务实例（单例模式）
    
    Args:
        collection_name: 集合名称
        
    Returns:
        SearchService: 搜索服务实例
    """
    global _search_service_instance
    
    if _search_service_instance is None:
        _search_service_instance = SearchService(collection_name)
    
    return _search_service_instance
