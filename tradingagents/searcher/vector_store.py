"""
向量存储模块 - 基于 ChromaDB + OpenAI Embeddings
提供文档的向量化存储和相似性查询功能
"""

import logging
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass

from tradingagents.llm_adapters.embeddings import OpenAIEmbeddings, create_dashscope_embeddings, HSBCEmbeddings
from tradingagents.agents.utils.chromadb_config import (
    get_default_chromadb_client,
    get_persistent_chromadb_client,
    DEFAULT_CHROMA_PERSIST_DIR,
)

try:
    import chromadb
    from chromadb.api.models.Collection import Collection
except ImportError:
    raise ImportError("请先安装 chromadb: pip install chromadb")

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """搜索结果数据类"""
    id: str
    content: str
    score: float
    metadata: Dict[str, Any]


class VectorStore:
    """
    向量存储类
    基于 ChromaDB 实现，支持文档的添加、插入、查询和删除
    """
    
    def __init__(
        self,
        collection_name: str = "default",
        embeddings: Optional[HSBCEmbeddings] = None,
        chroma_client = None,
        persist_directory: Optional[str] = None,
    ):
        """
        初始化向量存储
        
        Args:
            collection_name: 集合名称，用于区分不同类型的文档
            embeddings: Embeddings 实例，默认使用 DashScope
            chroma_client: ChromaDB 客户端，默认使用持久化客户端
            persist_directory: 数据持久化目录，默认使用 ./data/chromadb/
                           传 None 则使用内存模式（数据不保存）
        """
        self.collection_name = collection_name
        
        # 初始化 Embeddings
        if embeddings is None:
            try:
                self.embeddings = create_dashscope_embeddings()
                logger.info("✅ VectorStore 使用 DashScope Embeddings")
            except Exception as e:
                logger.warning(f"⚠️ DashScope 初始化失败，尝试 OpenAI: {e}")
                self.embeddings = OpenAIEmbeddings()
        else:
            self.embeddings = embeddings
        
        # 初始化 ChromaDB 客户端（默认使用持久化模式）
        if chroma_client:
            self.chroma_client = chroma_client
        elif persist_directory is None:
            # 默认使用持久化模式（写死的路径）
            self.chroma_client = get_default_chromadb_client()
            logger.info(f"📂 ChromaDB 持久化模式: {DEFAULT_CHROMA_PERSIST_DIR}")
        elif persist_directory == "":
            # 传空字符串使用内存模式
            from tradingagents.agents.utils.chromadb_config import get_optimal_chromadb_client
            self.chroma_client = get_optimal_chromadb_client()
            logger.info("📂 ChromaDB 内存模式（数据不会持久化）")
        else:
            # 使用自定义路径
            self.chroma_client = get_persistent_chromadb_client(persist_directory)
            logger.info(f"📂 ChromaDB 持久化模式: {persist_directory}")
        
        # 获取或创建集合
        self.collection = self._get_or_create_collection()
        
        logger.info(f"✅ VectorStore 初始化完成: collection={collection_name}")
    
    def _get_or_create_collection(self) -> Collection:
        """获取或创建集合"""
        try:
            collection = self.chroma_client.get_collection(name=self.collection_name)
            logger.debug(f"📂 获取已有集合: {self.collection_name}")
        except Exception:
            collection = self.chroma_client.create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}  # 使用余弦相似度
            )
            logger.info(f"📂 创建新集合: {self.collection_name}")
        return collection
    
    def insert(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        doc_id: Optional[str] = None
    ) -> str:
        """
        插入单条文档
        
        Args:
            content: 文档内容
            metadata: 元数据，如 {"source": "news", "date": "2024-01-01"}
            doc_id: 文档 ID，不传则自动生成
            
        Returns:
            str: 文档 ID
            
        Example:
            >>> store = VectorStore("stock_news")
            >>> doc_id = store.insert("股票A今日大涨5%", {"stock": "A", "type": "news"})
        """
        if not content or not content.strip():
            raise ValueError("文档内容不能为空")
        
        # 生成文档 ID
        if doc_id is None:
            import uuid
            doc_id = f"doc_{uuid.uuid4().hex[:12]}"
        
        # 生成向量
        embedding = self.embeddings.embed_query(content)
        
        # 元数据处理
        metadata = metadata or {}
        
        # 添加到 ChromaDB
        self.collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[metadata]
        )
        
        logger.debug(f"✅ 插入文档: {doc_id}, 内容长度: {len(content)}")
        return doc_id
    
    def add_documents(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[str]:
        """
        批量添加文档
        
        Args:
            documents: 文档列表，每项为 {"id": "...", "content": "...", "metadata": {...}}
                       id 和 metadata 为可选
            
        Returns:
            List[str]: 文档 ID 列表
            
        Example:
            >>> docs = [
            ...     {"content": "新闻1", "metadata": {"type": "news"}},
            ...     {"content": "新闻2", "metadata": {"type": "news"}},
            ... ]
            >>> ids = store.add_documents(docs)
        """
        if not documents:
            return []
        
        # 提取内容
        contents = []
        ids = []
        metadatas = []
        
        for i, doc in enumerate(documents):
            content = doc.get("content") or doc.get("text") or doc.get("document")
            if not content:
                logger.warning(f"⚠️ 跳过空内容文档: index={i}")
                continue
            
            contents.append(content)
            
            # ID
            doc_id = doc.get("id")
            if not doc_id:
                import uuid
                doc_id = f"doc_{uuid.uuid4().hex[:12]}"
            ids.append(doc_id)
            
            # 元数据
            meta = doc.get("metadata", {})
            metadatas.append(meta)
        
        if not contents:
            return []
        
        # 批量生成向量
        embeddings = self.embeddings.embed_documents(contents)
        
        # 批量添加到 ChromaDB
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=contents,
            metadatas=metadatas
        )
        
        logger.info(f"✅ 批量添加 {len(ids)} 个文档")
        return ids
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        相似性搜索
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            filter_metadata: 元数据过滤条件，如 {"type": "news"}
            
        Returns:
            List[SearchResult]: 搜索结果列表，按相似度降序排列
            
        Example:
            >>> results = store.search("股票A的最新消息", top_k=3)
            >>> for r in results:
            ...     print(f"{r.score:.3f}: {r.content[:50]}...")
        """
        if not query or not query.strip():
            return []
        
        # 生成查询向量
        query_embedding = self.embeddings.embed_query(query)
        
        # 构建过滤条件
        where_filter = None
        if filter_metadata:
            # ChromaDB 的过滤格式
            where_filter = {}
            for key, value in filter_metadata.items():
                where_filter[key] = value
        
        # 执行查询
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter if where_filter else None,
            include=["documents", "metadatas", "distances"]
        )
        
        # 解析结果
        search_results = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                content = results["documents"][0][i] if results["documents"] else ""
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                distance = results["distances"][0][i] if results["distances"] else 1.0
                
                # 距离转相似度 (余弦距离 0=最相似, 1=最不相似)
                score = 1.0 - float(distance)
                
                search_results.append(SearchResult(
                    id=doc_id,
                    content=content,
                    score=score,
                    metadata=metadata
                ))
        
        logger.debug(f"🔍 查询: '{query[:30]}...', 返回 {len(search_results)} 条结果")
        return search_results
    
    def delete(self, doc_id: Union[str, List[str]]) -> bool:
        """
        删除文档
        
        Args:
            doc_id: 文档 ID 或 ID 列表
            
        Returns:
            bool: 是否成功
            
        Example:
            >>> store.delete("doc_001")
            >>> store.delete(["doc_001", "doc_002"])
        """
        try:
            if isinstance(doc_id, str):
                ids = [doc_id]
            else:
                ids = list(doc_id)
            
            self.collection.delete(ids=ids)
            logger.info(f"✅ 删除 {len(ids)} 个文档")
            return True
        except Exception as e:
            logger.error(f"❌ 删除文档失败: {e}")
            return False
    
    def get(self, doc_id: str) -> Optional[SearchResult]:
        """
        根据 ID 获取文档
        
        Args:
            doc_id: 文档 ID
            
        Returns:
            SearchResult: 文档信息，不存在返回 None
        """
        try:
            result = self.collection.get(
                ids=[doc_id],
                include=["documents", "metadatas"]
            )
            
            if not result["ids"]:
                return None
            
            return SearchResult(
                id=result["ids"][0],
                content=result["documents"][0] if result["documents"] else "",
                score=1.0,  # 直接获取无相似度
                metadata=result["metadatas"][0] if result["metadatas"] else {}
            )
        except Exception as e:
            logger.error(f"❌ 获取文档失败: {e}")
            return None
    
    def count(self) -> int:
        """
        获取文档总数
        
        Returns:
            int: 文档数量
        """
        return self.collection.count()
    
    def clear(self) -> bool:
        """
        清空集合（删除所有文档）
        
        Returns:
            bool: 是否成功
        """
        try:
            self.chroma_client.delete_collection(name=self.collection_name)
            self.collection = self._get_or_create_collection()
            logger.info(f"✅ 清空集合: {self.collection_name}")
            return True
        except Exception as e:
            logger.error(f"❌ 清空集合失败: {e}")
            return False
    
    def list_all(self, limit: int = 100) -> List[SearchResult]:
        """
        列出所有文档
        
        Args:
            limit: 返回数量限制
            
        Returns:
            List[SearchResult]: 文档列表
        """
        try:
            results = self.collection.get(
                limit=limit,
                include=["documents", "metadatas"]
            )
            
            items = []
            for i, doc_id in enumerate(results["ids"]):
                content = results["documents"][i] if results["documents"] else ""
                metadata = results["metadatas"][i] if results["metadatas"] else {}
                
                items.append(SearchResult(
                    id=doc_id,
                    content=content,
                    score=1.0,
                    metadata=metadata
                ))
            
            return items
        except Exception as e:
            logger.error(f"❌ 列出文档失败: {e}")
            return []


# ==================== 便捷函数 ====================

def create_vector_store(
    collection_name: str = "default",
    use_dashscope: bool = True,
    persist_directory: Optional[str] = None,
) -> VectorStore:
    """
    创建向量存储实例的便捷函数
    
    Args:
        collection_name: 集合名称
        use_dashscope: 是否使用 DashScope（否则使用 OpenAI）
        persist_directory: 数据持久化目录，如 "./data/chromadb"
        
    Returns:
        VectorStore: 向量存储实例
    """
    if use_dashscope:
        embeddings = create_dashscope_embeddings()
    else:
        embeddings = OpenAIEmbeddings()
    
    return VectorStore(
        collection_name=collection_name,
        embeddings=embeddings,
        persist_directory=persist_directory
    )


# ==================== 使用示例 ====================

if __name__ == "__main__":
    # 示例1: 插入和查询
    print("=== VectorStore 使用示例 ===\n")
    
    try:
        # 创建存储（默认使用持久化模式，路径已写死）
        store = VectorStore(collection_name="demo_stock_news")
        # 如需内存模式：store = VectorStore(collection_name="demo", persist_directory="")
        
        # 插入单条文档
        print("1. 插入单条文档")
        doc_id = store.insert(
            content="平安银行今日发布财报，净利润同比增长15%",
            metadata={"stock": "000001", "type": "财报", "date": "2024-01-15"}
        )
        print(f"   文档 ID: {doc_id}")
        
        # 批量添加
        print("\n2. 批量添加文档")
        docs = [
            {"content": "万科A今日涨停，房地产板块集体上涨", "metadata": {"stock": "000002", "type": "新闻"}},
            {"content": "贵州茅台股价创新高，市值突破2万亿", "metadata": {"stock": "600519", "type": "新闻"}},
            {"content": "宁德时代发布新一代电池技术", "metadata": {"stock": "300750", "type": "公告"}},
        ]
        ids = store.add_documents(docs)
        print(f"   添加 {len(ids)} 个文档: {ids}")
        
        # 相似性查询
        print("\n3. 相似性查询")
        results = store.search("银行股业绩表现", top_k=3)
        for i, r in enumerate(results, 1):
            print(f"   {i}. [score={r.score:.3f}] {r.content[:40]}...")
        
        # 带过滤的查询
        print("\n4. 带过滤的查询 (type='新闻')")
        results = store.search("股价上涨", top_k=3, filter_metadata={"type": "新闻"})
        for i, r in enumerate(results, 1):
            print(f"   {i}. [score={r.score:.3f}] {r.content[:40]}...")
        
        # 获取文档总数
        print(f"\n5. 文档总数: {store.count()}")
        
        # 清理（可选）
        # store.clear()
        
    except Exception as e:
        print(f"示例运行失败: {e}")
