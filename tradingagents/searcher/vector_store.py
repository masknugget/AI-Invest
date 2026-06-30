"""
向量存储模块 - 基于 LanceDB + OpenAI Embeddings
提供文档的向量化存储和相似性查询功能
"""

import json
import logging
import uuid
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass

from tradingagents.llm_adapters.embeddings import OpenAIEmbeddings, create_hsbc_embeddings, HSBCEmbeddings
from tradingagents.agents.utils.lancedb_config import (
    get_default_lancedb_db,
    get_persistent_lancedb_db,
    get_memory_lancedb_db,
    DEFAULT_LANCE_PERSIST_DIR,
)

try:
    import lancedb
except ImportError:
    raise ImportError("请先安装 lancedb: pip install lancedb")

logger = logging.getLogger(__name__)


def _escape_sql_string(s: str) -> str:
    """转义 SQL 字符串中的单引号"""
    return s.replace("'", "''")


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
    基于 LanceDB 实现，支持文档的添加、插入、查询和删除
    """

    def __init__(
        self,
        collection_name: str = "default",
        embeddings: Optional[HSBCEmbeddings] = None,
        db_client = None,
        persist_directory: Optional[str] = None,
    ):
        """
        初始化向量存储

        Args:
            collection_name: 集合名称（LanceDB 中对应表名）
            embeddings: Embeddings 实例，默认使用 HSBC Embeddings
            db_client: LanceDB 数据库连接实例（可选）
            persist_directory: 数据持久化目录
                - None: 使用默认持久化路径 ./data/lancedb/
                - "": 使用内存模式（临时目录，数据不保存）
                - 其他: 使用指定路径
        """
        self.collection_name = collection_name
        self._memory_dir: Optional[str] = None

        # 初始化 Embeddings
        if embeddings is None:
            try:
                self.embeddings = create_hsbc_embeddings()
                logger.info("✅ VectorStore 使用 HSBC Embeddings")
            except Exception as e:
                logger.warning(f"⚠️ HSBC Embeddings 初始化失败: {e}")
                self.embeddings = OpenAIEmbeddings()
        else:
            self.embeddings = embeddings

        # 初始化 LanceDB 数据库连接
        if db_client is not None:
            self.db = db_client
        elif persist_directory is None:
            self.db = get_default_lancedb_db()
            logger.info(f"📂 LanceDB 持久化模式: {DEFAULT_LANCE_PERSIST_DIR}")
        elif persist_directory == "":
            self.db, self._memory_dir = get_memory_lancedb_db()
            logger.info("📂 LanceDB 内存模式（数据不会持久化）")
        else:
            self.db = get_persistent_lancedb_db(persist_directory)
            logger.info(f"📂 LanceDB 持久化模式: {persist_directory}")

        # 获取或创建表（延迟创建，首次插入时确定 schema）
        self.table = self._get_or_create_table()

        logger.info(f"✅ VectorStore 初始化完成: collection={collection_name}")

    def _get_or_create_table(self):
        """获取已有表，如不存在则返回 None（延迟到首次插入时创建）"""
        try:
            table = self.db.open_table(self.collection_name)
            logger.debug(f"📂 获取已有表: {self.collection_name}")
            return table
        except Exception:
            logger.info(f"📂 表不存在，将在首次插入时创建: {self.collection_name}")
            return None

    def _ensure_table(self, data: List[Dict[str, Any]]):
        """用第一批数据创建表（自动推断 schema）"""
        if self.table is not None:
            return
        self.table = self.db.create_table(self.collection_name, data=data)
        logger.info(f"📂 创建新表: {self.collection_name}")

    def _row_to_search_result(self, row: Dict[str, Any], distance: Optional[float] = None) -> SearchResult:
        """将 LanceDB 行数据转换为 SearchResult"""
        metadata_json = row.get("metadata_json") or "{}"
        try:
            metadata = json.loads(metadata_json)
        except json.JSONDecodeError:
            metadata = {}

        if distance is not None:
            # LanceDB cosine distance: 0=最相似, 2=最不相似
            # 转换为相似度分数: score = 1.0 - distance
            score = 1.0 - float(distance)
        else:
            score = 1.0

        return SearchResult(
            id=str(row.get("id", "")),
            content=str(row.get("content", "")),
            score=score,
            metadata=metadata,
        )

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

        if doc_id is None:
            doc_id = f"doc_{uuid.uuid4().hex[:12]}"

        embedding = self.embeddings.embed_query(content)
        metadata = metadata or {}

        data = [{
            "id": doc_id,
            "content": content,
            "vector": embedding,
            "metadata_json": json.dumps(metadata, ensure_ascii=False),
        }]

        if self.table is None:
            self._ensure_table(data)
        else:
            self.table.add(data)

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

        contents = []
        ids = []
        metadatas = []

        for i, doc in enumerate(documents):
            content = doc.get("content") or doc.get("text") or doc.get("document")
            if not content:
                logger.warning(f"⚠️ 跳过空内容文档: index={i}")
                continue

            contents.append(content)

            doc_id = doc.get("id")
            if not doc_id:
                doc_id = f"doc_{uuid.uuid4().hex[:12]}"
            ids.append(doc_id)

            meta = doc.get("metadata", {})
            metadatas.append(meta)

        if not contents:
            return []

        embeddings = self.embeddings.embed_documents(contents)

        data = []
        for doc_id, content, embedding, meta in zip(ids, contents, embeddings, metadatas):
            data.append({
                "id": doc_id,
                "content": content,
                "vector": embedding,
                "metadata_json": json.dumps(meta, ensure_ascii=False),
            })

        if self.table is None:
            self._ensure_table(data)
        else:
            self.table.add(data)

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

        if self.table is None:
            return []

        query_embedding = self.embeddings.embed_query(query)

        # 如果有过滤条件，多搜一些以便过滤后仍有足够结果
        search_limit = top_k * 5 if filter_metadata else top_k

        results_arrow = (
            self.table.search(query_embedding)
            .metric("cosine")
            .limit(search_limit)
            .to_arrow()
        )

        search_results = []
        for i in range(len(results_arrow)):
            row = {name: results_arrow.column(name)[i].as_py() for name in results_arrow.schema.names}
            distance = row.pop("_distance", None)
            result = self._row_to_search_result(row, distance=distance)
            search_results.append(result)

        # 应用元数据过滤（Python 层后过滤）
        if filter_metadata:
            filtered = []
            for r in search_results:
                if all(r.metadata.get(k) == v for k, v in filter_metadata.items()):
                    filtered.append(r)
            search_results = filtered[:top_k]
        else:
            search_results = search_results[:top_k]

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
        if self.table is None:
            return True

        try:
            if isinstance(doc_id, str):
                ids = [doc_id]
            else:
                ids = list(doc_id)

            if not ids:
                return True

            id_list = ", ".join(f"'{_escape_sql_string(id)}'" for id in ids)
            self.table.delete(f"id IN ({id_list})")
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
        if self.table is None:
            return None

        try:
            results_arrow = (
                self.table.search()
                .where(f"id = '{_escape_sql_string(doc_id)}'")
                .limit(1)
                .to_arrow()
            )

            if len(results_arrow) == 0:
                return None

            row = {name: results_arrow.column(name)[0].as_py() for name in results_arrow.schema.names}
            row.pop("_distance", None)
            return self._row_to_search_result(row)
        except Exception as e:
            logger.error(f"❌ 获取文档失败: {e}")
            return None

    def count(self) -> int:
        """
        获取文档总数

        Returns:
            int: 文档数量
        """
        if self.table is None:
            return 0
        return self.table.count_rows()

    def clear(self) -> bool:
        """
        清空集合（删除所有文档）

        Returns:
            bool: 是否成功
        """
        if self.table is None:
            return True

        try:
            self.table.delete("true")
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
        if self.table is None:
            return []

        try:
            results_arrow = (
                self.table.search()
                .limit(limit)
                .to_arrow()
            )

            items = []
            for i in range(len(results_arrow)):
                row = {name: results_arrow.column(name)[i].as_py() for name in results_arrow.schema.names}
                row.pop("_distance", None)
                items.append(self._row_to_search_result(row))

            return items
        except Exception as e:
            logger.error(f"❌ 列出文档失败: {e}")
            return []


# ==================== 便捷函数 ====================

def create_vector_store(
    collection_name: str = "default",
    use_hsbc: bool = True,
    persist_directory: Optional[str] = None,
) -> VectorStore:
    """
    创建向量存储实例的便捷函数

    Args:
        collection_name: 集合名称
        use_hsbc: 是否使用 HSBC Embeddings（否则使用 OpenAIEmbeddings）
        persist_directory: 数据持久化目录，如 "./data/lancedb"

    Returns:
        VectorStore: 向量存储实例
    """
    if use_hsbc:
        embeddings = create_hsbc_embeddings()
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
        # 创建存储（默认使用持久化模式）
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
        import traceback
        traceback.print_exc()
