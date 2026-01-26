"""
阿里百炼 OpenAI兼容适配器
为 TradingAgents 提供阿里百炼大模型的 OpenAI 兼容接口
利用百炼模型的原生 OpenAI 兼容性，无需额外的工具转换
"""

import os
from typing import Any, Dict, List, Optional, Union, Sequence
from langchain_openai import ChatOpenAI
from langchain_core.tools import BaseTool
from pydantic import Field, SecretStr
from ..config.config_manager import token_tracker

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger
from ..db.cache import cache

logger = get_logger('agents')


class ChatDashScopeOpenAI(ChatOpenAI):
    """
    阿里百炼 OpenAI 兼容适配器
    继承 ChatOpenAI，通过 OpenAI 兼容接口调用百炼模型
    利用百炼模型的原生 OpenAI 兼容性，支持原生 Function Calling
    """

    def __init__(self, **kwargs):
        """初始化 DashScope OpenAI 兼容客户端"""

        # 🔍 [DEBUG] 读取环境变量前的日志
        logger.info(f"🔍 [DashScope初始化] 开始初始化 ChatDashScopeOpenAI")
        logger.info(f"🔍 [DashScope初始化] kwargs 中是否包含 api_key: {'api_key' in kwargs}")

        # 🔥 优先使用 kwargs 中传入的 API Key（来自数据库配置）
        api_key_from_kwargs = kwargs.get("api_key")

        # 如果 kwargs 中没有 API Key 或者是 None，尝试从环境变量读取
        if not api_key_from_kwargs:
            # 导入 API Key 验证工具
            try:
                # 尝试从 app.utils 导入（后端环境）
                from app.utils.api_key_utils import is_valid_api_key
            except ImportError:
                # 如果导入失败，使用本地简化版本
                def is_valid_api_key(key):
                    if not key or len(key) <= 10:
                        return False
                    if key.startswith('your_') or key.startswith('your-'):
                        return False
                    if key.endswith('_here') or key.endswith('-here'):
                        return False
                    if '...' in key:
                        return False
                    return True

            # 尝试从环境变量读取 API Key
            env_api_key = os.getenv("DASHSCOPE_API_KEY")
            logger.info(f"🔍 [DashScope初始化] 从环境变量读取 DASHSCOPE_API_KEY: {'有值' if env_api_key else '空'}")

            # 验证环境变量中的 API Key 是否有效（排除占位符）
            if env_api_key and is_valid_api_key(env_api_key):
                logger.info(f"✅ [DashScope初始化] 环境变量中的 API Key 有效，长度: {len(env_api_key)}, 前10位: {env_api_key[:10]}...")
                api_key_from_kwargs = env_api_key
            elif env_api_key:
                logger.warning(f"⚠️ [DashScope初始化] 环境变量中的 API Key 无效（可能是占位符），将被忽略")
                api_key_from_kwargs = None
            else:
                logger.warning(f"⚠️ [DashScope初始化] DASHSCOPE_API_KEY 环境变量为空")
                api_key_from_kwargs = None
        else:
            logger.info(f"✅ [DashScope初始化] 使用 kwargs 中传入的 API Key（来自数据库配置）")

        # 设置 DashScope OpenAI 兼容接口的默认配置
        kwargs.setdefault("base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        kwargs["api_key"] = api_key_from_kwargs  # 🔥 使用验证后的 API Key
        kwargs.setdefault("model", "qwen-turbo")
        kwargs.setdefault("temperature", 0.1)
        kwargs.setdefault("max_tokens", 2000)

        # 检查 API 密钥和 base_url
        final_api_key = kwargs.get("api_key")
        final_base_url = kwargs.get("base_url")
        logger.info(f"🔍 [DashScope初始化] 最终使用的 API Key: {'有值' if final_api_key else '空'}")
        logger.info(f"🔍 [DashScope初始化] 最终使用的 base_url: {final_base_url}")

        if not final_api_key:
            logger.error(f"❌ [DashScope初始化] API Key 检查失败，即将抛出异常")
            raise ValueError(
                "DashScope API key not found. Please configure API key in web interface "
                "(Settings -> LLM Providers) or set DASHSCOPE_API_KEY environment variable."
            )

        # 调用父类初始化
        super().__init__(**kwargs)

        logger.info(f"✅ 阿里百炼 OpenAI 兼容适配器初始化成功")
        logger.info(f"   模型: {kwargs.get('model', 'qwen-turbo')}")

        # 兼容不同版本的属性名
        api_base = getattr(self, 'base_url', None) or getattr(self, 'openai_api_base', None) or kwargs.get('base_url', 'unknown')
        logger.info(f"   API Base: {api_base}")

    def _generate(self, *args, **kwargs):
        """重写生成方法，添加 token 使用量追踪"""

        # 调用父类的生成方法
        result = super()._generate(*args, **kwargs)

        # 追踪 token 使用量
        try:
            # 从结果中提取 token 使用信息
            if hasattr(result, 'llm_output') and result.llm_output:
                token_usage = result.llm_output.get('token_usage', {})

                input_tokens = token_usage.get('prompt_tokens', 0)
                output_tokens = token_usage.get('completion_tokens', 0)

                if input_tokens > 0 or output_tokens > 0:
                    # 生成会话ID
                    session_id = kwargs.get('session_id', f"dashscope_openai_{hash(str(args))%10000}")
                    analysis_type = kwargs.get('analysis_type', 'stock_analysis')

                    # 使用 TokenTracker 记录使用量
                    token_tracker.track_usage(
                        provider="dashscope",
                        model_name=self.model_name,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        session_id=session_id,
                        analysis_type=analysis_type
                    )

        except Exception as track_error:
            # token 追踪失败不应该影响主要功能
            logger.error(f"⚠️ Token 追踪失败: {track_error}")

        return result



def create_dashscope_openai_llm(
    model: str = "qwen-plus-latest",
    api_key: Optional[str] = None,
    temperature: float = 0.1,
    max_tokens: int = 2000,
    **kwargs
) -> ChatDashScopeOpenAI:
    """创建 DashScope OpenAI 兼容 LLM 实例的便捷函数"""

    return ChatDashScopeOpenAI(
        model=model,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs
    )


def get_jwt():
    return ""


class InternalLLM:
    @staticmethod
    def get_llm() -> ChatOpenAI:
        if 'jwt' in cache:
            jwt = cache['jwt']
        else:
            jwt = get_jwt()
            cache['jwt'] = jwt
        llm = create_dashscope_openai_llm(jwt=jwt)
        return llm
