"""
BM25 搜索模块 - 基于 bm25s 库实现
提供基于关键词的文档检索功能，与向量搜索形成互补
"""

import logging
import json
import pickle
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, asdict
from pathlib import Path

try:
    import bm25s
    import numpy as np
except ImportError:
    raise ImportError("请先安装 bm25s: pip install bm25s")

logger = logging.getLogger(__name__)


@dataclass
class BM25SearchResult:
    """BM25 搜索结果数据类"""
    id: str
    content: str
    score: float
    metadata: Dict[str, Any]
    rank: int


class BM25Store:
    """
    BM25 存储类
    基于 bm25s 库实现，支持文档的添加、索引和关键词搜索
    
    特点：
    - 基于关键词匹配，适合精确术语搜索
    - 不需要向量化，响应速度快
    - 与向量搜索互补，可混合使用
    """
    
    def __init__(
        self,
        collection_name: str = "default",
        persist_directory: Optional[str] = None,
        k1: float = 1.5,
        b: float = 0.75,
        delta: float = 0.5,
        method: str = "lucene",
    ):
        """
        初始化 BM25 存储
        
        Args:
            collection_name: 集合名称
            persist_directory: 数据持久化目录，默认不持久化
            k1: BM25 参数 k1，控制词频饱和度，默认 1.5
            b: BM25 参数 b，控制文档长度归一化，默认 0.75
            delta: BM25+ 参数，默认 0.5
            method: 计算方法，可选 "robertson", "lucene", "atire", "bm25l", "bm25+", 默认 "lucene"
        """
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        self.k1 = k1
        self.b = b
        self.delta = delta
        self.method = method
        
        # 存储数据
        self._documents: Dict[str, str] = {}  # id -> content
        self._metadatas: Dict[str, Dict] = {}  # id -> metadata
        self._bm25_retriever = None
        self._is_indexed = False
        
        # 如果指定了持久化目录，尝试加载
        if persist_directory:
            self._load()
        
        logger.info(f"✅ BM25Store 初始化: collection={collection_name}, method={method}")
    
    def _tokenize(self, texts: List[str]) -> List[List[str]]:
        """
        分词处理
        
        Args:
            texts: 文本列表
            
        Returns:
            分词后的 token 列表
        """
        # 使用 bm25s 的分词器
        return bm25s.tokenize(texts, stopwords="en")
    
    def _build_index(self) -> None:
        """构建 BM25 索引"""
        if not self._documents:
            self._bm25_retriever = None
            self._is_indexed = False
            return
        
        # 准备文档
        doc_ids = list(self._documents.keys())
        doc_contents = [self._documents[doc_id] for doc_id in doc_ids]
        
        # 分词
        corpus_tokens = self._tokenize(doc_contents)
        
        # 创建 BM25 索引
        self._bm25_retriever = bm25s.BM25(
            k1=self.k1,
            b=self.b,
            delta=self.delta,
            method=self.method,
        )
        self._bm25_retriever.index(corpus_tokens)
        
        # 保存 doc_ids 映射
        self._doc_id_mapping = doc_ids
        self._is_indexed = True
        
        logger.info(f"📊 BM25 索引构建完成: {len(doc_ids)} 个文档")
    
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
            metadata: 元数据
            doc_id: 文档 ID，不传则自动生成
            
        Returns:
            str: 文档 ID
        """
        if not content or not content.strip():
            raise ValueError("文档内容不能为空")
        
        # 生成文档 ID
        if doc_id is None:
            import uuid
            doc_id = f"doc_{uuid.uuid4().hex[:12]}"
        
        # 存储文档
        self._documents[doc_id] = content
        self._metadatas[doc_id] = metadata or {}
        
        # 标记需要重建索引
        self._is_indexed = False
        
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
        """
        if not documents:
            return []
        
        ids = []
        for doc in documents:
            content = doc.get("content") or doc.get("text") or doc.get("document")
            if not content:
                logger.warning(f"⚠️ 跳过空内容文档")
                continue
            
            doc_id = doc.get("id")
            metadata = doc.get("metadata", {})
            
            doc_id = self.insert(content, metadata, doc_id)
            ids.append(doc_id)
        
        logger.info(f"✅ 批量添加 {len(ids)} 个文档")
        return ids
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[BM25SearchResult]:
        """
        BM25 关键词搜索
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            filter_metadata: 元数据过滤条件（暂不支持，预留接口）
            
        Returns:
            List[BM25SearchResult]: 搜索结果列表，按 BM25 分数降序排列
        """
        if not query or not query.strip():
            return []
        
        # 确保索引已构建
        if not self._is_indexed:
            self._build_index()
        
        if not self._bm25_retriever:
            return []
        
        # 分词查询
        query_tokens = self._tokenize([query])
        
        # 执行搜索
        results, scores = self._bm25_retriever.retrieve(
            query_tokens,
            k=min(top_k, len(self._documents)),
            return_as="tuple"
        )
        
        # 解析结果
        search_results = []
        for rank, (doc_idx, score) in enumerate(zip(results[0], scores[0]), 1):
            doc_id = self._doc_id_mapping[doc_idx]
            content = self._documents[doc_id]
            metadata = self._metadatas.get(doc_id, {})
            
            # 元数据过滤（简单实现）
            if filter_metadata:
                skip = False
                for key, value in filter_metadata.items():
                    if metadata.get(key) != value:
                        skip = True
                        break
                if skip:
                    continue
            
            search_results.append(BM25SearchResult(
                id=doc_id,
                content=content,
                score=float(score),
                metadata=metadata,
                rank=rank
            ))
        
        logger.debug(f"🔍 BM25 查询: '{query[:30]}...', 返回 {len(search_results)} 条结果")
        return search_results
    
    def delete(self, doc_id: Union[str, List[str]]) -> bool:
        """
        删除文档
        
        Args:
            doc_id: 文档 ID 或 ID 列表
            
        Returns:
            bool: 是否成功
        """
        try:
            if isinstance(doc_id, str):
                ids = [doc_id]
            else:
                ids = list(doc_id)
            
            for did in ids:
                if did in self._documents:
                    del self._documents[did]
                    del self._metadatas[did]
            
            # 标记需要重建索引
            self._is_indexed = False
            
            logger.info(f"✅ 删除 {len(ids)} 个文档")
            return True
        except Exception as e:
            logger.error(f"❌ 删除文档失败: {e}")
            return False
    
    def get(self, doc_id: str) -> Optional[BM25SearchResult]:
        """
        根据 ID 获取文档
        
        Args:
            doc_id: 文档 ID
            
        Returns:
            BM25SearchResult: 文档信息，不存在返回 None
        """
        if doc_id not in self._documents:
            return None
        
        return BM25SearchResult(
            id=doc_id,
            content=self._documents[doc_id],
            score=1.0,
            metadata=self._metadatas.get(doc_id, {}),
            rank=0
        )
    
    def count(self) -> int:
        """
        获取文档总数
        
        Returns:
            int: 文档数量
        """
        return len(self._documents)
    
    def clear(self) -> bool:
        """
        清空所有文档
        
        Returns:
            bool: 是否成功
        """
        try:
            self._documents.clear()
            self._metadatas.clear()
            self._bm25_retriever = None
            self._is_indexed = False
            
            # 删除持久化文件
            if self.persist_directory:
                self._delete_persistent_files()
            
            logger.info(f"✅ 清空 BM25 集合: {self.collection_name}")
            return True
        except Exception as e:
            logger.error(f"❌ 清空集合失败: {e}")
            return False
    
    def list_all(self, limit: int = 100) -> List[BM25SearchResult]:
        """
        列出所有文档
        
        Args:
            limit: 返回数量限制
            
        Returns:
            List[BM25SearchResult]: 文档列表
        """
        results = []
        for i, (doc_id, content) in enumerate(self._documents.items()):
            if i >= limit:
                break
            results.append(BM25SearchResult(
                id=doc_id,
                content=content,
                score=1.0,
                metadata=self._metadatas.get(doc_id, {}),
                rank=i + 1
            ))
        return results
    
    def _get_persist_path(self) -> Path:
        """获取持久化路径"""
        base_path = Path(self.persist_directory) / self.collection_name
        base_path.mkdir(parents=True, exist_ok=True)
        return base_path
    
    def save(self) -> bool:
        """
        手动保存数据到磁盘
        
        Returns:
            bool: 是否成功
        """
        if not self.persist_directory:
            logger.warning("⚠️ 未指定 persist_directory，无法保存")
            return False
        
        try:
            persist_path = self._get_persist_path()
            
            # 保存文档和元数据
            data = {
                "documents": self._documents,
                "metadatas": self._metadatas,
                "config": {
                    "k1": self.k1,
                    "b": self.b,
                    "delta": self.delta,
                    "method": self.method,
                }
            }
            
            with open(persist_path / "data.pkl", "wb") as f:
                pickle.dump(data, f)
            
            # 保存 BM25 索引
            if self._bm25_retriever and self._is_indexed:
                self._bm25_retriever.save(persist_path / "bm25_index")
            
            logger.info(f"💾 BM25 数据已保存: {persist_path}")
            return True
        except Exception as e:
            logger.error(f"❌ 保存数据失败: {e}")
            return False
    
    def _save(self) -> bool:
        """内部保存方法（自动调用）"""
        return self.save()
    
    def _load(self) -> bool:
        """从磁盘加载数据"""
        try:
            persist_path = self._get_persist_path()
            data_file = persist_path / "data.pkl"
            
            if not data_file.exists():
                logger.info(f"📂 未找到持久化数据: {data_file}")
                return False
            
            # 加载文档和元数据
            with open(data_file, "rb") as f:
                data = pickle.load(f)
            
            self._documents = data["documents"]
            self._metadatas = data["metadatas"]
            
            # 加载 BM25 索引
            index_path = persist_path / "bm25_index"
            if index_path.exists():
                self._bm25_retriever = bm25s.BM25.load(index_path)
                self._doc_id_mapping = list(self._documents.keys())
                self._is_indexed = True
                logger.info(f"📂 BM25 索引已从磁盘加载")
            else:
                self._is_indexed = False
            
            logger.info(f"📂 BM25 数据已加载: {len(self._documents)} 个文档")
            return True
        except Exception as e:
            logger.error(f"❌ 加载数据失败: {e}")
            return False
    
    def _delete_persistent_files(self) -> None:
        """删除持久化文件"""
        try:
            persist_path = self._get_persist_path()
            import shutil
            if persist_path.exists():
                shutil.rmtree(persist_path)
        except Exception as e:
            logger.error(f"❌ 删除持久化文件失败: {e}")


class HybridSearcher:
    """
    混合搜索器
    结合向量搜索（语义）和 BM25 搜索（关键词），提供更全面的搜索结果
    """
    
    def __init__(
        self,
        vector_store=None,
        bm25_store: Optional[BM25Store] = None,
        vector_weight: float = 0.5,
        bm25_weight: float = 0.5,
    ):
        """
        初始化混合搜索器
        
        Args:
            vector_store: 向量存储实例（可选）
            bm25_store: BM25 存储实例（可选）
            vector_weight: 向量搜索权重
            bm25_weight: BM25 搜索权重
        """
        self.vector_store = vector_store
        self.bm25_store = bm25_store
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight
        
        logger.info(f"✅ HybridSearcher 初始化: vector_weight={vector_weight}, bm25_weight={bm25_weight}")
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        混合搜索
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            filter_metadata: 元数据过滤条件
            
        Returns:
            List[Dict]: 合并后的搜索结果
        """
        results_map = {}
        
        # 向量搜索
        if self.vector_store:
            try:
                vector_results = self.vector_store.search(
                    query, 
                    top_k=top_k * 2,  # 获取更多结果用于融合
                    filter_metadata=filter_metadata
                )
                for r in vector_results:
                    results_map[r.id] = {
                        "id": r.id,
                        "content": r.content,
                        "metadata": r.metadata,
                        "vector_score": r.score * self.vector_weight,
                        "bm25_score": 0.0,
                        "sources": ["vector"],
                    }
            except Exception as e:
                logger.error(f"向量搜索失败: {e}")
        
        # BM25 搜索
        if self.bm25_store:
            try:
                bm25_results = self.bm25_store.search(
                    query, 
                    top_k=top_k * 2,
                    filter_metadata=filter_metadata
                )
                for r in bm25_results:
                    if r.id in results_map:
                        results_map[r.id]["bm25_score"] = r.score * self.bm25_weight
                        results_map[r.id]["sources"].append("bm25")
                    else:
                        results_map[r.id] = {
                            "id": r.id,
                            "content": r.content,
                            "metadata": r.metadata,
                            "vector_score": 0.0,
                            "bm25_score": r.score * self.bm25_weight,
                            "sources": ["bm25"],
                        }
            except Exception as e:
                logger.error(f"BM25 搜索失败: {e}")
        
        # 计算综合得分
        merged_results = []
        for item in results_map.values():
            # 使用加权平均或取最大值
            if "vector" in item["sources"] and "bm25" in item["sources"]:
                # 两种搜索都命中，加权平均
                item["score"] = item["vector_score"] + item["bm25_score"]
            elif "vector" in item["sources"]:
                item["score"] = item["vector_score"]
            else:
                item["score"] = item["bm25_score"]
            merged_results.append(item)
        
        # 按分数排序
        merged_results.sort(key=lambda x: x["score"], reverse=True)
        
        # 返回 top_k
        return merged_results[:top_k]


# ==================== 便捷函数 ====================

def create_bm25_store(
    collection_name: str = "default",
    persist_directory: Optional[str] = None,
    **kwargs
) -> BM25Store:
    """
    创建 BM25 存储实例的便捷函数
    
    Args:
        collection_name: 集合名称
        persist_directory: 数据持久化目录
        **kwargs: 其他参数传递给 BM25Store
        
    Returns:
        BM25Store: BM25 存储实例
    """
    return BM25Store(
        collection_name=collection_name,
        persist_directory=persist_directory,
        **kwargs
    )


# ==================== 使用示例 ====================

if __name__ == "__main__":
    print("=== BM25Store 使用示例 ===\n")
    
    try:
        # 创建 BM25 存储
        store = BM25Store(collection_name="demo_news")
        
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
            {"content": "银行股今日整体表现强劲，多只个股上涨", "metadata": {"type": "新闻"}},
        ]
        ids = store.add_documents(docs)
        print(f"   添加 {len(ids)} 个文档: {ids}")
        
        # BM25 搜索
        print("\n3. BM25 关键词搜索")
        results = store.search("银行 财报", top_k=3)
        for i, r in enumerate(results, 1):
            print(f"   {i}. [score={r.score:.3f}] {r.content[:40]}...")
        
        # 获取文档总数
        print(f"\n4. 文档总数: {store.count()}")
        
        # 清理
        # store.clear()
        
    except Exception as e:
        print(f"示例运行失败: {e}")
        import traceback
        traceback.print_exc()
