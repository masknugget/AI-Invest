# -*- coding: utf-8 -*-
"""
news_reader.llms 测试：配置注入 / messages 构造 / 同步与异步调用的重试与空响应。

所有真实 LLM 调用均 mock，不依赖网络与 API key。

运行方式：
    python tests/test_recommender/test_news_reader/test_llms.py
"""
import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

import httpx
from openai import APITimeoutError

import recommender.news_reader.llms as llms

for _k in ("NEWS_READER_API_KEY", "DASHSCOPE_API_KEY", "OPENAI_API_KEY",
           "NEWS_READER_BASE_URL", "NEWS_READER_MODEL", "NEWS_READER_ANALYST_MODEL"):
    os.environ.pop(_k, None)


class _FakeMessage:
    def __init__(self, content: Optional[str]):
        self.content = content


class _FakeChoice:
    def __init__(self, content: Optional[str]):
        self.message = _FakeMessage(content)


class _FakeCompletion:
    def __init__(self, content: Optional[str]):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    """前 failures 次抛 APITimeoutError，之后返回固定内容。"""

    def __init__(self, failures=0, content: Optional[str] = '{"ok": true}'):
        self.failures = failures
        self.content = content
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        if self.calls <= self.failures:
            raise APITimeoutError(request=httpx.Request("POST", "https://example.com"))
        return _FakeCompletion(self.content)


class _FakeAsyncCompletions:
    def __init__(self, failures=0, content: Optional[str] = '{"ok": true}'):
        self.failures = failures
        self.content = content
        self.calls = 0

    async def create(self, **kwargs):
        self.calls += 1
        if self.calls <= self.failures:
            raise APITimeoutError(request=httpx.Request("POST", "https://example.com"))
        return _FakeCompletion(self.content)


class _FakeChat:
    def __init__(self, completions):
        self.completions = completions


class _FakeClient:
    def __init__(self, failures=0, content: Optional[str] = '{"ok": true}'):
        self.chat = _FakeChat(_FakeCompletions(failures, content))


class _FakeAsyncClient:
    def __init__(self, failures=0, content: Optional[str] = '{"ok": true}'):
        self.chat = _FakeChat(_FakeAsyncCompletions(failures, content))


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


# ============================================================================
# 配置注入
# ============================================================================

def test_api_key_priority():
    print("=== 测试 API key 优先级：NEWS_READER > DASHSCOPE > OPENAI ===")
    try:
        llms.get_api_key()
        raise AssertionError("无 key 应抛 RuntimeError")
    except RuntimeError:
        pass

    os.environ["OPENAI_API_KEY"] = "sk-openai"
    assert llms.get_api_key() == "sk-openai"
    os.environ["DASHSCOPE_API_KEY"] = "sk-ds"
    assert llms.get_api_key() == "sk-ds"
    os.environ["NEWS_READER_API_KEY"] = "sk-nr"
    assert llms.get_api_key() == "sk-nr"
    for k in ("NEWS_READER_API_KEY", "DASHSCOPE_API_KEY", "OPENAI_API_KEY"):
        os.environ.pop(k)
    print("✅ 通过")


def test_base_url_and_models():
    print("=== 测试 base_url 与模型配置 ===")
    assert llms.get_base_url() == llms.DEFAULT_BASE_URL
    os.environ["NEWS_READER_BASE_URL"] = "https://custom.example.com/v1"
    assert llms.get_base_url() == "https://custom.example.com/v1"
    os.environ.pop("NEWS_READER_BASE_URL")

    assert llms.get_default_model() == llms.DEFAULT_MODEL
    os.environ["NEWS_READER_MODEL"] = "qwen-flash"
    assert llms.get_default_model() == "qwen-flash"
    # ANALYST 缺省回退默认模型
    assert llms.get_analyst_model() == "qwen-flash"
    os.environ["NEWS_READER_ANALYST_MODEL"] = "qwen-max"
    assert llms.get_analyst_model() == "qwen-max"
    os.environ.pop("NEWS_READER_ANALYST_MODEL")
    os.environ.pop("NEWS_READER_MODEL")
    print("✅ 通过")


# ============================================================================
# messages 构造（历史 tuple bug 回归）
# ============================================================================

def test_build_messages():
    print("=== 测试 messages 构造（tuple bug 回归）===")
    m = llms._build_messages("你好", "你是助手")
    assert isinstance(m, list) and len(m) == 2
    assert m[0]["role"] == "system" and m[1]["role"] == "user"
    m2 = llms._build_messages("你好", None)
    assert isinstance(m2, list) and len(m2) == 1 and m2[0]["role"] == "user"
    print("✅ 通过")


# ============================================================================
# chat_once / achat_once
# ============================================================================

def test_chat_once_success_and_model():
    print("=== 测试 chat_once 正常调用与 model 参数 ===")
    fake = _FakeClient()
    orig = llms._sync_client
    llms._sync_client = lambda: fake
    try:
        resp = llms.chat_once("hi", model="custom-model")
        assert resp == '{"ok": true}'
        assert fake.chat.completions.calls == 1
    finally:
        llms._sync_client = orig
    print("✅ 通过")


def test_chat_once_retry_then_success():
    print("=== 测试 chat_once 超时重试后成功 ===")
    fake = _FakeClient(failures=2)
    orig_client, orig_sleep = llms._sync_client, llms.time.sleep
    llms._sync_client = lambda: fake
    llms.time.sleep = lambda s: None
    try:
        assert llms.chat_once("hi") == '{"ok": true}'
        assert fake.chat.completions.calls == 3
    finally:
        llms._sync_client, llms.time.sleep = orig_client, orig_sleep
    print("✅ 通过")


def test_chat_once_retry_exhausted():
    print("=== 测试 chat_once 重试耗尽抛异常 ===")
    fake = _FakeClient(failures=99)
    orig_client, orig_sleep = llms._sync_client, llms.time.sleep
    llms._sync_client = lambda: fake
    llms.time.sleep = lambda s: None
    try:
        try:
            llms.chat_once("hi")
            raise AssertionError("应抛 APITimeoutError")
        except APITimeoutError:
            pass
        assert fake.chat.completions.calls == llms._MAX_RETRIES + 1
    finally:
        llms._sync_client, llms.time.sleep = orig_client, orig_sleep
    print("✅ 通过")


def test_chat_once_empty_response_raises():
    print("=== 测试 LLM 空响应抛错 ===")
    fake = _FakeClient(content=None)
    orig = llms._sync_client
    llms._sync_client = lambda: fake
    try:
        try:
            llms.chat_once("hi")
            raise AssertionError("空响应应抛 RuntimeError")
        except RuntimeError as e:
            assert "空" in str(e)
    finally:
        llms._sync_client = orig
    print("✅ 通过")


def test_achat_once_retry():
    print("=== 测试 achat_once 异步重试 ===")
    fake = _FakeAsyncClient(failures=1)
    orig_client = llms._async_client

    async def _no_sleep(s):
        return None

    orig_sleep = llms.asyncio.sleep
    llms._async_client = lambda: fake
    llms.asyncio.sleep = _no_sleep
    try:
        assert _run(llms.achat_once("hi")) == '{"ok": true}'
        assert fake.chat.completions.calls == 2
    finally:
        llms._async_client, llms.asyncio.sleep = orig_client, orig_sleep
    print("✅ 通过")


def run_all_tests():
    tests = [
        ("api_key_priority", test_api_key_priority),
        ("base_url_and_models", test_base_url_and_models),
        ("build_messages", test_build_messages),
        ("chat_once_success_and_model", test_chat_once_success_and_model),
        ("chat_once_retry_then_success", test_chat_once_retry_then_success),
        ("chat_once_retry_exhausted", test_chat_once_retry_exhausted),
        ("chat_once_empty_response_raises", test_chat_once_empty_response_raises),
        ("achat_once_retry", test_achat_once_retry),
    ]
    passed = failed = 0
    for name, func in tests:
        try:
            func()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"❌ {name} failed: {e}")
    print(f"\n=== {passed} passed, {failed} failed ===")
    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if run_all_tests() else 1)
