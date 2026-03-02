"""
BM25 关键词搜索服务
提供基于关键词的文档检索功能，与向量搜索形成互补
"""

import logging
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime

from tradingagents.searcher import BM25Store
from app.config.config import Config

logger = logging.getLogger("webapi")


# ==================== 模型定义 ====================

class BM25SearchRequest(BaseModel):
    """BM25 搜索请求"""
    query: str
    top_k: int = 5
    filter_metadata: Optional[Dict[str, Any]] = None


class BM25SearchResultItem(BaseModel):
    """BM25 搜索结果项"""
    id: str
    content: str
    score: float
    metadata: Dict[str, Any]
    rank: int


class BM25DocumentInsert(BaseModel):
    """BM25 文档插入请求"""
    content: str
    metadata: Optional[Dict[str, Any]] = None
    doc_id: Optional[str] = None


class BM25DocumentInsertResponse(BaseModel):
    """BM25 文档插入响应"""
    doc_id: str
    content_preview: str
    status: str


class BM25SearchStats(BaseModel):
    """BM25 搜索统计"""
    collection_name: str
    total_documents: int
    last_updated: Optional[str] = None
    index_built: bool = False


# ==================== 核心服务类 ====================

class BM25SearchService:
    """
    BM25 关键词搜索服务
    包装 BM25Store，提供业务层接口
    """
    
    def __init__(
        self, 
        collection_name: str = None,
        persist_directory: str = None,
        k1: float = None,
        b: float = None,
        delta: float = None,
        method: str = None
    ):
        """
        初始化 BM25 搜索服务
        
        Args:
            collection_name: 集合名称，默认从配置读取
            persist_directory: 数据持久化目录，默认从配置读取
            k1: BM25 k1 参数，默认从配置读取
            b: BM25 b 参数，默认从配置读取
            delta: BM25+ delta 参数，默认从配置读取
            method: BM25 计算方法，默认从配置读取
        """
        self.collection_name = collection_name or Config.bm25_default_collection
        self.persist_directory = persist_directory or Config.bm25_persist_directory
        self.k1 = k1 if k1 is not None else Config.bm25_k1
        self.b = b if b is not None else Config.bm25_b
        self.delta = delta if delta is not None else Config.bm25_delta
        self.method = method or Config.bm25_method
        
        try:
            self.store = BM25Store(
                collection_name=self.collection_name,
                persist_directory=self.persist_directory,
                k1=self.k1,
                b=self.b,
                delta=self.delta,
                method=self.method
            )
            logger.info(f"✅ BM25SearchService 初始化: collection={self.collection_name}, method={self.method}")
        except Exception as e:
            logger.error(f"❌ BM25Store 初始化失败: {e}")
            # 创建一个内存模式的 store
            self.store = BM25Store(
                collection_name=self.collection_name,
                k1=self.k1,
                b=self.b,
                delta=self.delta,
                method=self.method
            )
            logger.warning(f"⚠️ 使用内存模式（无持久化）")
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[BM25SearchResultItem]:
        """
        BM25 关键词搜索
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            filter_metadata: 元数据过滤条件
            
        Returns:
            List[BM25SearchResultItem]: 搜索结果列表
        """
        try:
            results = self.store.search(
                query=query,
                top_k=top_k,
                filter_metadata=filter_metadata
            )
            
            # 转换为 BM25SearchResultItem 模型
            return [
                BM25SearchResultItem(
                    id=r.id,
                    content=r.content,
                    score=r.score,
                    metadata=r.metadata,
                    rank=r.rank
                )
                for r in results
            ]
        except Exception as e:
            logger.error(f"❌ BM25 搜索失败: {e}")
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
            
            # 保存索引
            self.store.save()
            
            logger.info(f"✅ BM25 添加文档: {doc_id}")
            return doc_id
        except Exception as e:
            logger.error(f"❌ BM25 添加文档失败: {e}")
            raise
    
    def add_documents(self, documents: List[BM25DocumentInsert]) -> List[str]:
        """
        批量添加文档
        
        Args:
            documents: 文档列表
            
        Returns:
            List[str]: 文档ID列表
        """
        try:
            # 转换为 BM25Store 格式
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
            
            # 保存索引
            self.store.save()
            
            logger.info(f"✅ BM25 批量添加文档: {len(doc_ids)} 条")
            return doc_ids
        except Exception as e:
            logger.error(f"❌ BM25 批量添加文档失败: {e}")
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
                # 保存索引
                self.store.save()
                logger.info(f"✅ BM25 删除文档: {doc_id}")
            else:
                logger.warning(f"⚠️ BM25 删除文档失败: {doc_id}")
            return result
        except Exception as e:
            logger.error(f"❌ BM25 删除文档异常: {e}")
            return False
    
    def get_document(self, doc_id: str) -> Optional[BM25SearchResultItem]:
        """
        获取单个文档
        
        Args:
            doc_id: 文档ID
            
        Returns:
            BM25SearchResultItem: 文档信息
        """
        try:
            result = self.store.get(doc_id)
            if result:
                return BM25SearchResultItem(
                    id=result.id,
                    content=result.content,
                    score=result.score,
                    metadata=result.metadata,
                    rank=result.rank
                )
            return None
        except Exception as e:
            logger.error(f"❌ BM25 获取文档失败: {e}")
            return None
    
    def get_stats(self) -> BM25SearchStats:
        """
        获取统计信息
        
        Returns:
            BM25SearchStats: 统计数据
        """
        try:
            count = self.store.count()
            index_built = self.store._is_indexed
            return BM25SearchStats(
                collection_name=self.collection_name,
                total_documents=count,
                last_updated=datetime.now().isoformat(),
                index_built=index_built
            )
        except Exception as e:
            logger.error(f"❌ BM25 获取统计失败: {e}")
            return BM25SearchStats(
                collection_name=self.collection_name,
                total_documents=0,
                last_updated=None,
                index_built=False
            )
    
    def list_documents(self, limit: int = 100) -> List[BM25SearchResultItem]:
        """
        列出所有文档
        
        Args:
            limit: 数量限制
            
        Returns:
            List[BM25SearchResultItem]: 文档列表
        """
        try:
            results = self.store.list_all(limit=limit)
            return [
                BM25SearchResultItem(
                    id=r.id,
                    content=r.content,
                    score=r.score,
                    metadata=r.metadata,
                    rank=r.rank
                )
                for r in results
            ]
        except Exception as e:
            logger.error(f"❌ BM25 列出文档失败: {e}")
            return []
    
    def save(self) -> bool:
        """
        手动保存索引
        
        Returns:
            bool: 是否成功
        """
        try:
            return self.store.save()
        except Exception as e:
            logger.error(f"❌ BM25 保存索引失败: {e}")
            return False
    
    def clear(self) -> bool:
        """
        清空所有文档
        
        Returns:
            bool: 是否成功
        """
        try:
            return self.store.clear()
        except Exception as e:
            logger.error(f"❌ BM25 清空失败: {e}")
            return False
    
    @staticmethod
    def get_config() -> Dict[str, Any]:
        """获取 BM25 配置信息"""
        return {
            "persist_directory": Config.bm25_persist_directory,
            "default_collection": Config.bm25_default_collection,
            "k1": Config.bm25_k1,
            "b": Config.bm25_b,
            "delta": Config.bm25_delta,
            "method": Config.bm25_method,
        }


# ==================== 便捷函数 ====================

_bm25_search_service_instance: Optional[BM25SearchService] = None


def get_bm25_search_service(
    collection_name: str = None,
    persist_directory: str = None,
    k1: float = None,
    b: float = None,
    delta: float = None,
    method: str = None
) -> BM25SearchService:
    """
    获取 BM25 搜索服务实例（单例模式）
    
    默认使用 Config 类中的配置，也可通过参数覆盖
    
    Args:
        collection_name: 集合名称，默认从 Config.bm25_default_collection 读取
        persist_directory: 持久化目录，默认从 Config.bm25_persist_directory 读取
        k1: BM25 k1 参数，默认从 Config.bm25_k1 读取
        b: BM25 b 参数，默认从 Config.bm25_b 读取
        delta: BM25+ delta 参数，默认从 Config.bm25_delta 读取
        method: BM25 计算方法，默认从 Config.bm25_method 读取
        
    Returns:
        BM25SearchService: BM25 搜索服务实例
    """
    global _bm25_search_service_instance
    
    if _bm25_search_service_instance is None:
        # 使用 Config 中的默认值
        _bm25_search_service_instance = BM25SearchService(
            collection_name=collection_name,
            persist_directory=persist_directory,
            k1=k1,
            b=b,
            delta=delta,
            method=method
        )
    
    return _bm25_search_service_instance


def reset_bm25_search_service():
    """重置 BM25 搜索服务实例（用于测试或重新初始化）"""
    global _bm25_search_service_instance
    _bm25_search_service_instance = None
    logger.info("BM25SearchService 实例已重置")
