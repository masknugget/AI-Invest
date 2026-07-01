"""
HSBC Internal Embedding Adapter
为 TradingAgents 提供 HSBC 内部 AI Gateway 的 Embedding 接口支持

注意：每次调用都会重新初始化 HTTP Client 和获取认证 Token，
避免长期保持连接导致认证过期问题。
"""

import os
import ssl
import uuid
import logging
from typing import List, Optional

import httpx
import truststore
import openai
from openai import OpenAI

logger = logging.getLogger(__name__)


# --- Default Configuration (can be overridden via env vars) ---
DEFAULT_BASE_URL = "https://gaip-api-uat.hsbc-12152296-gaipuat-dev.dev.gcp.cloud.hk.hsbc/etiv-ssvc-aigateway-ea-chatcompletion-uat-internal-proxy/v1/ap"
DEFAULT_USER = "UC0003983"
DEFAULT_AUTH_METHOD = "B2B"  # or "S2B"
DEFAULT_SERVICE_ACCOUNT = "HK-SVCAT-IPO-DEV"
DEFAULT_PASSWORD = "75F1-f80dCD4B2"
DEFAULT_IB2B_DSP_URL = "https://cmb-ib2b-dsp-pprod-ap.hk.hsbc:8443/dsp/rest-sts/DSP_IB2B/IB2B_tokenTranslator?_action=translate"
DEFAULT_MODEL = "text-embedding-3-large"


def _build_hsbc_http_client() -> httpx.Client:
    """构建支持 HSBC 内部 SSL 证书的 HTTP Client"""
    ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    return httpx.Client(http2=True, verify=ctx, timeout=30.0)


def _get_hsbc_auth_headers(
    client: httpx.Client,
    auth_method: str,
    service_account: str,
    password: str,
    ib2b_dsp_url: str,
    amtoken: str,
) -> dict:
    """
    获取 HSBC 认证 Headers

    Args:
        client: HTTP Client
        auth_method: 认证方式 "B2B" 或 "S2B"
        service_account: B2B 服务账号
        password: B2B 密码
        ib2b_dsp_url: B2B DSP URL
        amtoken: S2B 模式的 AM Token

    Returns:
        dict: 认证 Headers
    """
    if auth_method.upper() == "B2B":
        payload = {
            "input_token_state": {
                "token_type": "CREDENTIAL",
                "username": service_account,
                "password": password,
            },
            "output_token_state": {"token_type": "JWT"},
        }
        rsp = client.post(ib2b_dsp_url, json=payload)
        rsp.raise_for_status()
        token = rsp.json().get("issued_token")
        if not token:
            raise RuntimeError("issued_token missing in B2B response")
        return {"X-HSBC-E2E-Trust-Token": token}

    if auth_method.upper() == "S2B":
        if not amtoken:
            raise RuntimeError("AMTOKEN is required when AUTH_METHOD=S2B")
        return {"Authorization": f"session {amtoken}"}

    raise RuntimeError(f"Unsupported AUTH_METHOD: {auth_method}")


class OpenAIEmbeddings:
    """
    HSBC 内部 AI Gateway Embedding 适配器
    （保持 OpenAIEmbeddings 类名以兼容现有代码）

    注意：每次调用 embed_query/embed_documents 都会重新初始化 client
    和获取新的 auth token，避免认证过期问题。
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = None,
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
            base_url: HSBC API 基础 URL
            model: Embedding 模型名称，默认 text-embedding-3-large
            user: 用户 ID
            auth_method: 认证方式 "B2B" 或 "S2B"
            service_account: B2B 服务账号
            password: B2B 密码
            ib2b_dsp_url: B2B DSP URL
            amtoken: S2B 模式的 AM Token
            **kwargs: 其他参数（兼容旧接口，会被忽略）
        """
        # 存储配置，不保存 client
        raw_base = (base_url or os.getenv("HSBC_BASE_URL", DEFAULT_BASE_URL)).rstrip("/")
        self.base_url = raw_base.removesuffix("/chat/completions")
        self.model = model or os.getenv("HSBC_EMBEDDING_MODEL", DEFAULT_MODEL)
        self.user = user or os.getenv("HSBC_USER", DEFAULT_USER)
        self.auth_method = auth_method or os.getenv("HSBC_AUTH_METHOD", DEFAULT_AUTH_METHOD)
        self.service_account = service_account or os.getenv("HSBC_SERVICE_ACCOUNT", DEFAULT_SERVICE_ACCOUNT)
        self.password = password or os.getenv("HSBC_PASSWORD", DEFAULT_PASSWORD)
        self.ib2b_dsp_url = ib2b_dsp_url or os.getenv("HSBC_IB2B_DSP_URL", DEFAULT_IB2B_DSP_URL)
        self.amtoken = amtoken or os.getenv("HSBC_AMTOKEN", "")

        logger.info(f"✅ HSBC Embeddings 配置初始化: model={self.model}, auth={self.auth_method}")

    def _create_client(self) -> tuple[openai.OpenAI, dict]:
        """
        创建新的 OpenAI Client 和获取认证 Headers

        Returns:
            tuple: (client, auth_headers)
        """
        # http_client = _build_hsbc_http_client()
        #
        # auth_headers = _get_hsbc_auth_headers(
        #     http_client,
        #     self.auth_method,
        #     self.service_account,
        #     self.password,
        #     self.ib2b_dsp_url,
        #     self.amtoken,
        # )
        #
        # client = openai.OpenAI(
        #     api_key="N/A",
        #     base_url=self.base_url,
        #     http_client=http_client,
        #     default_headers={
        #         "Content-Type": "application/json",
        #         "x-correlation-id": str(uuid.uuid4()),
        #         "x-usersession-id": str(uuid.uuid4()),
        #     },
        # )
        #
        # return client, auth_headers
        client = OpenAI(
            # 若没有配置环境变量，请用阿里云百炼API Key将下行替换为：api_key="sk-xxx",
            # 各地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
            api_key=r'sk-d6e82744ac33451fbe0cff05687a3695',
            # 以下是北京地域base-url，如果使用新加坡地域的模型，需要将base_url替换为：https://dashscope-intl.aliyuncs.com/compatible-mode/v1
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        return client

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

        # 每次调用都重新初始化 client 和获取 auth
        # client, auth_headers = self._create_client()
        client = self._create_client()

        try:
            response = client.embeddings.create(
                model="text-embedding-v4",
                input=text
            )
            return response.data[0].embedding
        finally:
            # 确保关闭 http client
            client.close()

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
                # 每个 batch 重新获取 client 和 auth
                # client, auth_headers = self._create_client()
                client = self._create_client()

                try:
                    response = client.embeddings.create(
                        model="text-embedding-v4",
                        input=batch
                    )
                    # response = client.embeddings.create(
                    #     model=self.model,
                    #     input=batch,
                    #     user=self.user,
                    #     extra_headers=auth_headers,
                    # )
                    batch_embeddings = [item.embedding for item in response.data]
                    all_embeddings.extend(batch_embeddings)

                    if total > batch_size:
                        logger.debug(f"向量化进度: {min(i + batch_size, total)}/{total}")
                finally:
                    client.close()

            except Exception as e:
                logger.error(f"批量向量化失败 (batch {i//batch_size + 1}): {e}")
                # 失败时逐个处理
                logger.warning(f"尝试逐条处理本批次 {len(batch)} 条数据...")
                for text in batch:
                    try:
                        embedding = self.embed_query(text)
                        all_embeddings.append(embedding)
                    except Exception as e2:
                        logger.error(f"单条向量化失败: {e2}")
                        all_embeddings.append([])

        return all_embeddings


def create_embeddings(
    api_key: Optional[str] = None,
    model: str = None
) -> OpenAIEmbeddings:
    """

    Args:
        api_key: API Key（会被忽略，仅保持兼容）
        model: 模型名称，默认从环境变量读取

    Returns:
        OpenAIEmbeddings: Embeddings 实例
    """
    return OpenAIEmbeddings(
        model=model,
    )


def embedding_text(input_text: str) -> List[float]:
    """
    简单的文本向量化函数（兼容旧接口）

    Args:
        input_text: 输入文本

    Returns:
        List[float]: 向量
    """
    embeddings = create_embeddings()
    return embeddings.embed_query(input_text)


# 保留 HSBCEmbeddings 别名以便明确使用
HSBCEmbeddings = OpenAIEmbeddings


def create_hsbc_embeddings(
    model: str = None,
    auth_method: str = None,
    **kwargs
) -> OpenAIEmbeddings:
    """
    创建 HSBC Embeddings 实例的便捷函数

    Args:
        model: 模型名称，默认 text-embedding-3-large
        auth_method: 认证方式，默认从环境变量读取
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
    # 示例1: 使用默认配置
    print("=== HSBC Embeddings 使用示例 ===\n")

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