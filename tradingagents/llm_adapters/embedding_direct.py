"""
Direct HSBC AI Gateway Embedding Client

直接调用 HSBC 内部 AI Gateway 的 embedding 接口。
环境相关配置统一来自 app.config.config.Config；切到生产环境时只需在
app/config/config.py 中打开对应 Config 的注释即可。
"""

import os
import uuid
import time
import logging
import urllib3
from typing import List, Optional

import requests
from app.config.config import Config

logger = logging.getLogger(__name__)

# Suppress InsecureRequestWarning caused by verify=False in B2B DSP calls
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Embedding 专用默认值（app.config.config.Config 中未包含 embedding 模型）
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-large"

# 以下别名均来自 Config，避免在多处重复维护相同的 endpoint/账号信息
BASE_URL = f"{Config.BASE_URL_API.rstrip('/')}/embeddings"
DEFAULT_USER_ID = Config.USER_ID
DEFAULT_AUTH_METHOD = os.getenv("AUTH_METHOD", "B2B")  # "B2B" or "S2B"
DEFAULT_SERVICE_ACCOUNT = Config.SERVICE_ACCOUNT
DEFAULT_PASSWORD = Config.PASSWORD
DEFAULT_IB2B_DSP_URL = Config.IB2B_DSP_URL

# 保持旧代码对 DEFAULT_MODEL 的导入兼容
DEFAULT_MODEL = DEFAULT_EMBEDDING_MODEL


def _get_service_account_jwt(
    service_account: str = DEFAULT_SERVICE_ACCOUNT,
    password: str = DEFAULT_PASSWORD,
    ib2b_dsp_url: str = DEFAULT_IB2B_DSP_URL,
) -> str:
    """Fetches a JWT from the B2B DSP service."""
    logger.info("开始大模型 B2B JWT 验证")
    time_s = time.time()
    payload = {
        "input_token_state": {
            "token_type": "CREDENTIAL",
            "username": service_account,
            "password": password,
        },
        "output_token_state": {"token_type": "JWT"},
    }
    try:
        resp = requests.post(ib2b_dsp_url, json=payload, verify=False, timeout=500)
        resp.raise_for_status()
    finally:
        time_e = time.time() - time_s
        logger.info("大模型 B2B JWT 验证耗时: %.3fs", time_e)

    data = resp.json()
    jwt = data.get("issued_token")
    if not jwt:
        raise RuntimeError(f"JWT not found in B2B response: {data}")
    return jwt


def _get_s2b_auth_header(amtoken: str) -> dict:
    """Builds S2B authentication header."""
    if not amtoken:
        raise RuntimeError("AMTOKEN is required when AUTH_METHOD=S2B")
    return {"Authorization": f"session {amtoken}"}


def get_hsbc_auth_headers(
    auth_method: Optional[str] = None,
    service_account: Optional[str] = None,
    password: Optional[str] = None,
    ib2b_dsp_url: Optional[str] = None,
    amtoken: Optional[str] = None,
) -> dict:
    """
    获取 HSBC 认证 Headers。

    Args:
        auth_method: 认证方式 "B2B" 或 "S2B"
        service_account: B2B 服务账号
        password: B2B 密码
        ib2b_dsp_url: B2B DSP URL
        amtoken: S2B 模式的 AM Token

    Returns:
        dict: 仅包含认证字段的 headers
    """
    auth_method = (auth_method or DEFAULT_AUTH_METHOD).upper()
    if auth_method == "B2B":
        token = _get_service_account_jwt(
            service_account or DEFAULT_SERVICE_ACCOUNT,
            password or DEFAULT_PASSWORD,
            ib2b_dsp_url or DEFAULT_IB2B_DSP_URL,
        )
        return {"X-HSBC-E2E-Trust-Token": token}
    if auth_method == "S2B":
        return _get_s2b_auth_header(amtoken or os.getenv("AMTOKEN", ""))
    raise RuntimeError(f"Unsupported AUTH_METHOD: {auth_method}")


def embed_texts_direct(
    texts: List[str],
    model: Optional[str] = None,
    user: Optional[str] = None,
    auth_method: Optional[str] = None,
    service_account: Optional[str] = None,
    password: Optional[str] = None,
    ib2b_dsp_url: Optional[str] = None,
    amtoken: Optional[str] = None,
    base_url: Optional[str] = None,
) -> List[List[float]]:
    """
    直接调用 HSBC AI Gateway embedding 接口。

    Args:
        texts: 待向量化的文本列表
        model: 模型名称（覆盖默认值）
        user: 用户 ID（覆盖默认值）
        auth_method, service_account, password, ib2b_dsp_url, amtoken: 认证参数（覆盖默认值）
        base_url: embedding 接口 URL（覆盖默认值）

    Returns:
        List[List[float]]: 与输入顺序一致的向量列表
    """
    if not texts:
        return []

    auth_headers = get_hsbc_auth_headers(
        auth_method=auth_method,
        service_account=service_account,
        password=password,
        ib2b_dsp_url=ib2b_dsp_url,
        amtoken=amtoken,
    )

    headers = {
        **auth_headers,
        "Content-Type": "application/json",
        "x-correlation-id": str(uuid.uuid4()),
        "x-usersession-id": str(uuid.uuid4()),
    }

    data = {
        "model": model or DEFAULT_EMBEDDING_MODEL,
        "input": texts,
        "user": user or DEFAULT_USER_ID,
        "stream": False,
    }

    logger.info(
        "开始调用 HSBC embedding 接口: model=%s, texts=%d",
        data["model"],
        len(texts),
    )
    time_s = time.time()
    try:
        response = requests.post(
            base_url or BASE_URL,
            headers=headers,
            json=data,
            timeout=120,
        )
        response.raise_for_status()
    finally:
        time_e = time.time() - time_s
        logger.info("HSBC embedding 接口调用耗时: %.3fs", time_e)

    out_data = response.json()
    embeddings = []
    for idx, item in enumerate(out_data.get("data", [])):
        embedding = item.get("embedding")
        if embedding is None:
            raise RuntimeError(f"embedding missing for item {idx}: {item}")
        embeddings.append(embedding)

    if len(embeddings) != len(texts):
        raise RuntimeError(
            f"embedding count mismatch: expected {len(texts)}, got {len(embeddings)}"
        )

    return embeddings


# ==================== 使用示例 ====================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # 直接调用（使用 app.config.config.Config 中的当前环境配置）
    texts = ["你是谁"]
    vectors = embed_texts_direct(texts, model="text-embedding-3-large")
    print(f"文本数量: {len(texts)}")
    print(f"向量数量: {len(vectors)}")
    if vectors:
        print(f"向量维度: {len(vectors[0])}")
        print(f"前5个值: {vectors[0][:5]}")
