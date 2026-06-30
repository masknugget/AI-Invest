"""
HSBC Internal Embedding Adapter (Direct HTTP)
为 TradingAgents 提供 HSBC 内部 AI Gateway 的 Embedding 接口支持

注意：每次调用都会重新获取认证 Token 并直接发起 HTTP 请求，
避免长期保持连接导致认证过期问题。
"""

import os
import logging
from typing import List, Optional

from .embedding_direct import (
    embed_texts_direct,
    DEFAULT_MODEL,
    BASE_URL,
    DEFAULT_USER_ID,
    DEFAULT_AUTH_METHOD,
    DEFAULT_SERVICE_ACCOUNT,
    DEFAULT_PASSWORD,
    DEFAULT_IB2B_DSP_URL,
)

logger = logging.getLogger(__name__)


class OpenAIEmbeddings:
    """
    HSBC 内部 AI Gateway Embedding 适配器
    （保持 OpenAIEmbeddings 类名以兼容现有代码）

    注意：每次调用 embed_query/embed_documents 都会重新获取新的 auth token，
    通过 tradingagents.llm_adapters.embedding_direct.embed_texts_direct
    直接发起 HTTP 请求，避免认证过期问题。
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        user: Optional[str] = None,
        auth_method: Optional[str] = None,
        service_account: Optional[str] = None,
        password: Optional[str] = None,
        ib2b_dsp_url: Optional[str] = None,
        amtoken: Optional[str] = None,
        **kwargs
    ):
        """
        初始化 HSBC Embeddings 配置

        Args:
            api_key: API Key (HSBC 接口不需要，会被忽略)
            base_url: HSBC API 基础 URL（覆盖 Config 默认值）
            model: Embedding 模型名称（覆盖 Config 默认值）
            user: 用户 ID（覆盖 Config 默认值）
            auth_method: 认证方式 "B2B" 或 "S2B"（覆盖 Config 默认值）
            service_account: B2B 服务账号（覆盖 Config 默认值）
            password: B2B 密码（覆盖 Config 默认值）
            ib2b_dsp_url: B2B DSP URL（覆盖 Config 默认值）
            amtoken: S2B 模式的 AM Token
            **kwargs: 其他参数（兼容旧接口，会被忽略）
        """
        # 存储配置，不保存 client；每次调用都通过 embedding_direct 重新建连/取 token
        self.base_url = base_url or os.getenv("HSBC_BASE_URL", BASE_URL)
        self.model = model or os.getenv("HSBC_EMBEDDING_MODEL", DEFAULT_MODEL)
        self.user = user or os.getenv("HSBC_USER", DEFAULT_USER_ID)
        self.auth_method = auth_method or os.getenv("HSBC_AUTH_METHOD", DEFAULT_AUTH_METHOD)
        self.service_account = service_account or os.getenv("HSBC_SERVICE_ACCOUNT", DEFAULT_SERVICE_ACCOUNT)
        self.password = password or os.getenv("HSBC_PASSWORD", DEFAULT_PASSWORD)
        self.ib2b_dsp_url = ib2b_dsp_url or os.getenv("HSBC_IB2B_DSP_URL", DEFAULT_IB2B_DSP_URL)
        self.amtoken = amtoken or os.getenv("HSBC_AMTOKEN", "")

        logger.info(
            "✅ HSBC Embeddings 配置初始化: model=%s, auth=%s, base_url=%s",
            self.model,
            self.auth_method,
            self.base_url,
        )

    def embed_query(self, text: str) -> List[float]:
        """
        单个文本向量化

        Args:
            text: 输入文本

        Returns:
            List[float]: 向量
        """
        if not text:
            return []

        # 每次调用都通过 embedding_direct 重新获取 auth 并发起请求
        embeddings = embed_texts_direct(
            texts=[text],
            model=self.model,
            user=self.user,
            auth_method=self.auth_method,
            service_account=self.service_account,
            password=self.password,
            ib2b_dsp_url=self.ib2b_dsp_url,
            amtoken=self.amtoken,
            base_url=self.base_url,
        )

        if not embeddings:
            raise RuntimeError("Embedding response is empty for single text")

        return embeddings[0]

    def embed_documents(
        self,
        texts: List[str],
        batch_size: int = 10
    ) -> List[List[float]]:
        """
        批量文本向量化

        Args:
            texts: 文本列表
            batch_size: 每批处理的文本数量

        Returns:
            List[List[float]]: 向量列表
        """
        if not texts:
            return []

        all_embeddings = []
        total = len(texts)

        for i in range(0, total, batch_size):
            batch = texts[i:i + batch_size]

            try:
                # 每个 batch 重新获取 auth 并发起请求
                batch_embeddings = embed_texts_direct(
                    texts=batch,
                    model=self.model,
                    user=self.user,
                    auth_method=self.auth_method,
                    service_account=self.service_account,
                    password=self.password,
                    ib2b_dsp_url=self.ib2b_dsp_url,
                    amtoken=self.amtoken,
                    base_url=self.base_url,
                )

                if len(batch_embeddings) != len(batch):
                    raise RuntimeError(
                        f"embedding count mismatch: expected {len(batch)}, got {len(batch_embeddings)}"
                    )

                all_embeddings.extend(batch_embeddings)

                if total > batch_size:
                    logger.debug("向量化进度: %d/%d", min(i + batch_size, total), total)

            except Exception as e:
                logger.error("批量向量化失败 (batch %d): %s", i // batch_size + 1, e)
                # 失败时逐个处理
                logger.warning("尝试逐条处理本批次 %d 条数据...", len(batch))
                for text in batch:
                    try:
                        embedding = self.embed_query(text)
                        all_embeddings.append(embedding)
                    except Exception as e2:
                        logger.error("单条向量化失败: %s", e2)
                        all_embeddings.append([])

        return all_embeddings


def embedding_text(input_text: str) -> List[float]:
    """
    简单的文本向量化函数（兼容旧接口）

    Args:
        input_text: 输入文本

    Returns:
        List[float]: 向量
    """
    embeddings = create_hsbc_embeddings()
    return embeddings.embed_query(input_text)


# 保留 HSBCEmbeddings 别名以便明确使用
HSBCEmbeddings = OpenAIEmbeddings


def create_hsbc_embeddings(
    model: Optional[str] = None,
    auth_method: Optional[str] = None,
    **kwargs
) -> OpenAIEmbeddings:
    """
    创建 HSBC Embeddings 实例的便捷函数

    Args:
        model: 模型名称，默认从 Config 读取
        auth_method: 认证方式，默认从 Config 读取
        **kwargs: 其他配置参数

    Returns:
        OpenAIEmbeddings: Embeddings 实例
    """
    return OpenAIEmbeddings(
        model=model,
        auth_method=auth_method,
        **kwargs
    )


# ==================== 使用示例 ====================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=== HSBC Embeddings (Direct) 使用示例 ===\n")

    try:
        # 创建 embeddings 实例
        embeddings = create_hsbc_embeddings()

        # 单条文本向量化
        print("1. 单条文本向量化")
        text = "HSBC 银行今日发布财报"
        vector = embeddings.embed_query(text)
        print(f"   文本: {text}")
        print(f"   向量维度: {len(vector)}")
        print(f"   前5个值: {vector[:5]}")

        # 批量文本向量化
        print("\n2. 批量文本向量化")
        texts = ["你好", "Hello", "Bonjour"]
        vectors = embeddings.embed_documents(texts)
        print(f"   文本数量: {len(texts)}")
        print(f"   向量数量: {len(vectors)}")
        for i, v in enumerate(vectors):
            print(f"   [{i}] 维度: {len(v)}")

    except Exception as e:
        print(f"示例运行失败: {e}")
