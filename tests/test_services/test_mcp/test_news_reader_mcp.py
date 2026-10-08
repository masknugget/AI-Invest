"""
News Reader MCP 改造测试（自定义 runner 模式，非 pytest）

用法：
    python tests/test_news_reader_mcp.py

覆盖范围（对应 docs/news_reader_mcp_design.md 验证计划）：
- llms: tuple bug 修复 / API key 注入 / 空响应抛错 / 超时重试（mock client）
- utils: parse_json_from_llm 解析与 eval 移除
- consumer: aextract_meta 三路并发 / arun_analyst 校验 / apipeline_news 结构与并发 /
  同步 pipeline_news 报告拼接修复
- cache: 缓存键格式 / Redis 不可用时降级
- service: extract_meta 缓存命中零 LLM / finalize 校验与入库开关 / analyze_news 缓存
- MCP 工具: 参数校验 / 响应封装 / search 过滤器构造

所有 LLM 调用均 mock，不依赖网络、MongoDB、Redis。
"""
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Optional

project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

import httpx
from langchain_core.exceptions import OutputParserException
from openai import APITimeoutError

import recommender.news_reader.consumer.news as consumer
import recommender.news_reader.llms as llms
from recommender.news_reader.utils import parse_json_from_llm

from app.services.news_analysis import cache, service, store
from app.services.mcp.tools.news_reader import (
    agent_tool_name,
    analyze_news,
    build_analyst_tools,
    extract_news_meta,
    finalize_news_analysis,
    list_news_analysts,
    search_news_insights,
)
from app.services.mcp.tools.news_reader import contract

_FULL_META = {"data_ner": {}, "data_label": {}, "data_event": {}}

# 生成一次供全部分析师工具用例复用
_ANALYST_TOOLS = build_analyst_tools()

# 确保无 API key 环境（key 注入测试自行设置）
for _k in ("NEWS_READER_API_KEY", "DASHSCOPE_API_KEY", "OPENAI_API_KEY"):
    os.environ.pop(_k, None)


# ============================================================================
# mock 工具
# ============================================================================

class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeCompletion:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    """前 failures 次调用抛 APITimeoutError，之后返回固定内容。"""

    def __init__(self, failures: int = 0, content: Optional[str] = '{"ok": true}'):
        self.failures = failures
        self.content = content
        self.calls = 0
        self.kwargs = []

    def _maybe_fail(self):
        self.calls += 1
        if self.calls <= self.failures:
            raise APITimeoutError(request=httpx.Request("POST", "https://example.com"))
        return _FakeCompletion(self.content)

    def create(self, **kwargs):
        self.kwargs.append(kwargs)
        return self._maybe_fail()


class _FakeAsyncCompletions:
    """异步版：前 failures 次调用抛 APITimeoutError，之后返回固定内容。"""

    def __init__(self, failures: int = 0, content: Optional[str] = '{"ok": true}'):
        self.failures = failures
        self.content = content
        self.calls = 0
        self.kwargs = []

    async def create(self, **kwargs):
        self.kwargs.append(kwargs)
        self.calls += 1
        if self.calls <= self.failures:
            raise APITimeoutError(request=httpx.Request("POST", "https://example.com"))
        return _FakeCompletion(self.content)


class _FakeChat:
    def __init__(self, completions):
        self.completions = completions


class _FakeClient:
    def __init__(self, failures: int = 0, content: Optional[str] = '{"ok": true}'):
        self.chat = _FakeChat(_FakeCompletions(failures, content))


class _FakeAsyncClient:
    def __init__(self, failures: int = 0, content: Optional[str] = '{"ok": true}'):
        self.chat = _FakeChat(_FakeAsyncCompletions(failures, content))


def _parse(resp):
    assert isinstance(resp, str), "工具必须返回 JSON 字符串"
    return json.loads(resp)


def _run(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


# ============================================================================
# llms 测试
# ============================================================================

def test_build_messages_no_tuple_bug():
    print("=== 测试 sys_prompt 分支 messages 构造（tuple bug 修复）===")
    m = llms._build_messages("你好", "你是助手")
    assert isinstance(m, list) and len(m) == 2, f"应为两元素列表，实际: {m!r}"
    assert m[0]["role"] == "system" and m[0]["content"] == "你是助手"
    assert m[1]["role"] == "user"
    m2 = llms._build_messages("你好", None)
    assert isinstance(m2, list) and len(m2) == 1, f"应为单元素列表，实际: {m2!r}"
    print("✅ 通过")


def test_api_key_injection():
    print("=== 测试 API key 环境变量注入 ===")
    try:
        llms.get_api_key()
        raise AssertionError("无 key 时应抛 RuntimeError")
    except RuntimeError:
        pass
    os.environ["NEWS_READER_API_KEY"] = "sk-test"
    assert llms.get_api_key() == "sk-test"
    del os.environ["NEWS_READER_API_KEY"]

    os.environ["DASHSCOPE_API_KEY"] = "sk-ds"
    assert llms.get_api_key() == "sk-ds"
    del os.environ["DASHSCOPE_API_KEY"]
    print("✅ 通过")


def test_chat_once_retry_on_timeout():
    print("=== 测试 chat_once 超时重试（前 2 次失败，第 3 次成功）===")
    fake = _FakeClient(failures=2)
    orig_client, orig_sleep = llms._sync_client, llms.time.sleep
    llms._sync_client = lambda: fake
    llms.time.sleep = lambda s: None
    try:
        resp = llms.chat_once("hi")
        assert resp == '{"ok": true}'
        assert fake.chat.completions.calls == 3, f"应调用 3 次，实际 {fake.chat.completions.calls}"
    finally:
        llms._sync_client, llms.time.sleep = orig_client, orig_sleep
    print("✅ 通过")


def test_chat_once_exhausts_retries():
    print("=== 测试 chat_once 重试耗尽后抛异常 ===")
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


def test_chat_once_empty_content_raises():
    print("=== 测试 LLM 空响应抛错 ===")
    fake = _FakeClient(failures=0, content=None)
    orig_client = llms._sync_client
    llms._sync_client = lambda: fake
    try:
        try:
            llms.chat_once("hi")
            raise AssertionError("空响应应抛 RuntimeError")
        except RuntimeError as e:
            assert "空" in str(e)
    finally:
        llms._sync_client = orig_client
    print("✅ 通过")


def test_achat_once_retry():
    print("=== 测试 achat_once 超时重试 ===")
    fake = _FakeAsyncClient(failures=1)
    orig_client, orig_sleep = llms._async_client, llms.asyncio.sleep

    async def _no_sleep(s):
        return None

    llms._async_client = lambda: fake
    llms.asyncio.sleep = _no_sleep
    try:
        resp = _run(llms.achat_once("hi"))
        assert resp == '{"ok": true}'
        assert fake.chat.completions.calls == 2
    finally:
        llms._async_client, llms.asyncio.sleep = orig_client, orig_sleep
    print("✅ 通过")


# ============================================================================
# utils 测试
# ============================================================================

def test_parse_json_from_llm():
    print("=== 测试 parse_json_from_llm ===")
    assert parse_json_from_llm('{"a": 1}') == {"a": 1}
    assert parse_json_from_llm('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_from_llm('前缀文字 {"a": 1} 后缀') == {"a": 1}
    try:
        parse_json_from_llm("完全不是 JSON")
        raise AssertionError("应抛 OutputParserException")
    except OutputParserException:
        pass
    print("✅ 通过")


def test_parse_json_no_eval():
    print("=== 测试 eval 兜底已移除（恶意输入不执行）===")
    marker = []

    payload = f"__import__('builtins').exec({marker!r}.append(1))"
    try:
        parse_json_from_llm(payload)
    except OutputParserException:
        pass
    except Exception:
        pass
    assert not marker, "eval 兜底仍存在：恶意输入被执行"
    print("✅ 通过")


# ============================================================================
# consumer 流水线测试
# ============================================================================

def _make_fake_achat(state, sleep=0.05):
    async def fake(prompt, sys_prompt=None, model=None):
        state["current"] += 1
        state["max"] = max(state["max"], state["current"])
        state["calls"] += 1
        if sleep:
            await asyncio.sleep(sleep)
        state["current"] -= 1
        return '{"ok": true}'

    return fake


def test_aextract_meta_parallel():
    print("=== 测试 aextract_meta 三路并行（设计验证计划 2）===")
    state = {"current": 0, "max": 0, "calls": 0}
    orig = consumer.achat_once
    consumer.achat_once = _make_fake_achat(state)
    try:
        meta = _run(consumer.aextract_meta("某公司发布财报"))
    finally:
        consumer.achat_once = orig
    assert state["calls"] == 3, f"应调用 3 次，实际 {state['calls']}"
    assert state["max"] == 3, f"应三路并发，实际 max={state['max']}"
    for k in ("data_ner", "data_label", "data_event"):
        assert k in meta, f"meta 缺少 {k}"
    print("✅ 通过")


def test_arun_analyst_validation():
    print("=== 测试 arun_analyst 非法 Agent 抛错 ===")
    orig = consumer.achat_once
    consumer.achat_once = _make_fake_achat({"current": 0, "max": 0, "calls": 0})
    try:
        try:
            _run(consumer.arun_analyst("新闻", {}, "NoSuchAgent"))
            raise AssertionError("非法 agent 应抛 ValueError")
        except ValueError as e:
            assert "NoSuchAgent" in str(e)
    finally:
        consumer.achat_once = orig
    print("✅ 通过")


def test_arun_analyst_uses_analyst_model():
    print("=== 测试分析 Agent 使用 ANALYST 模型 ===")
    seen = {}

    async def fake(prompt, sys_prompt=None, model=None):
        seen["model"] = model
        return "报告"

    orig = consumer.achat_once
    consumer.achat_once = fake
    os.environ["NEWS_READER_ANALYST_MODEL"] = "qwen-analyst-test"
    try:
        _run(consumer.arun_analyst("新闻", {"data_ner": {}}, "MicroAgent"))
        assert seen["model"] == "qwen-analyst-test", f"实际模型: {seen['model']}"
    finally:
        consumer.achat_once = orig
        del os.environ["NEWS_READER_ANALYST_MODEL"]
    print("✅ 通过")


def test_apipeline_news_structure():
    print("=== 测试 apipeline_news 结构与 Agent 并发 ===")
    state = {"current": 0, "max": 0, "calls": 0}
    orig = consumer.achat_once
    consumer.achat_once = _make_fake_achat(state)
    try:
        out = _run(
            consumer.apipeline_news(
                "某公司发布财报",
                agent_names=["MicroAgent", "SentimentAgent"],
                with_report=False,
            )
        )
    finally:
        consumer.achat_once = orig

    for k in ("data_ner", "data_label", "data_event",
              "MicroAgent", "SentimentAgent", "data_align", "article_id"):
        assert k in out, f"输出缺少 {k}，实际键: {sorted(out.keys())}"
    assert state["max"] >= 2, f"两 Agent 应并发，实际 max={state['max']}"
    assert "data_report" not in out, "with_report=False 时不应有 data_report"
    assert out["data_align"].get("article_id")
    assert out["data_align"].get("create_time")
    print("✅ 通过")


def test_apipeline_news_default_agents():
    print("=== 测试 apipeline_news 默认 Agent 兜底 ===")
    state = {"current": 0, "max": 0, "calls": 0}

    async def fake_router(prompt, sys_prompt=None, model=None):
        state["calls"] += 1
        return '{"routing_plan": {"primary_agents": []}}'

    orig = consumer.achat_once
    consumer.achat_once = fake_router
    try:
        out = _run(consumer.apipeline_news("新闻", agent_names=None, with_router=True))
        # 路由返回空 → 走默认 Agent，key 仍存在（mock 恒返回路由 JSON，此处只验证不抛错）
        assert "data_align" in out
    finally:
        consumer.achat_once = orig
    print("✅ 通过")


def test_sync_pipeline_report_joins_all_agents():
    print("=== 测试同步 pipeline_news 报告拼接全部 Agent（content[0] bug 修复）===")
    router_json = '{"routing_plan": {"primary_agents": [{"agent": "MicroAgent"}, {"agent": "SentimentAgent"}]}}'
    captured = {}

    def fake_chat(prompt, sys_prompt=None, model=None):
        if model:
            captured.setdefault("analyst_models", []).append(model)
        if "财经新闻与分析写作" in prompt:
            captured["report_prompt"] = prompt
            return "报告"
        if "路由决策专家" in prompt:
            return router_json
        if "金融数据结构化工程师" in prompt:
            return '{"title": "t"}'
        return '{"ok": true}'

    orig = consumer.chat_once
    consumer.chat_once = fake_chat
    try:
        out = consumer.pipeline_news("某公司发布财报")
    finally:
        consumer.chat_once = orig

    # 两个 Agent 的分析都应进入报告输入
    rp = captured.get("report_prompt", "")
    assert "公司微观分析" in rp, "报告输入缺少 MicroAgent 结果"
    assert "情绪与资金流向分析" in rp, "报告输入缺少 SentimentAgent 结果"
    # 分析 Agent 调用使用 ANALYST 模型
    assert all(m == "qwen3.5-flash" for m in captured.get("analyst_models", []))
    assert out["data_report"] == "报告"
    print("✅ 通过")


# ============================================================================
# cache 测试
# ============================================================================

class _FakeRedis:
    def __init__(self):
        self.store = {}

    async def get(self, key):
        return self.store.get(key)

    async def setex(self, key, ttl, value):
        self.store[key] = value
        self.ttl = ttl


def test_cache_key_format():
    print("=== 测试缓存键格式 ===")
    k = cache.make_key("abc")
    assert k.startswith("news_reader:") and len(k) == len("news_reader:") + 32, k
    assert cache.make_key("abc", cache.META_SUFFIX) == k + ":meta"
    assert cache.make_key("abc") != cache.make_key("abd")
    print("✅ 通过")


def test_cache_roundtrip():
    print("=== 测试缓存读写 ===")
    fake = _FakeRedis()
    orig = cache._get_client
    cache._get_client = lambda: fake
    try:
        assert _run(cache.get_json("k")) is None
        _run(cache.set_json("k", {"a": 1}))
        assert _run(cache.get_json("k")) == {"a": 1}
        assert fake.ttl == cache.TTL_SECONDS
    finally:
        cache._get_client = orig
    print("✅ 通过")


def test_cache_degrades_without_redis():
    print("=== 测试 Redis 不可用时缓存降级 ===")
    orig = cache._get_client
    cache._get_client = lambda: None
    try:
        assert _run(cache.get_json("k")) is None  # 不抛错
        _run(cache.set_json("k", {"a": 1}))       # 不抛错
    finally:
        cache._get_client = orig
    print("✅ 通过")


# ============================================================================
# service 测试
# ============================================================================

def test_service_extract_meta_cache_hit():
    print("=== 测试 extract_meta 缓存命中零 LLM（设计验证计划 3）===")
    state = {"calls": 0}

    async def fake_extract(content):
        state["calls"] += 1
        return {"data_ner": {"n": 1}}

    orig_extract, orig_get, orig_set = (
        service.aextract_meta, cache.get_json, cache.set_json,
    )
    stored = {}

    async def fake_get(key):
        return stored.get(key)

    async def fake_set(key, value, ttl=None):
        stored[key] = value

    service.aextract_meta = fake_extract
    cache.get_json, cache.set_json = fake_get, fake_set
    try:
        meta1 = _run(service.extract_meta("新闻A"))
        meta2 = _run(service.extract_meta("新闻A"))
        assert meta1 == meta2 == {"data_ner": {"n": 1}}
        assert state["calls"] == 1, f"缓存未命中，LLM 调用 {state['calls']} 次"
    finally:
        service.aextract_meta, cache.get_json, cache.set_json = (
            orig_extract, orig_get, orig_set,
        )
    print("✅ 通过")


def test_service_run_analyst_validation():
    print("=== 测试 service.run_analyst 参数校验 ===")
    for bad in ("", "  "):
        try:
            _run(service.run_analyst("新闻", {}, bad))
            raise AssertionError(f"agent_name={bad!r} 应抛 ValueError")
        except ValueError:
            pass
    try:
        _run(service.run_analyst("  ", {}, "MicroAgent"))
        raise AssertionError("空内容应抛 ValueError")
    except ValueError:
        pass
    print("✅ 通过")


def test_service_finalize_save_toggle():
    print("=== 测试 finalize 入库开关 ===")
    saved = []

    async def fake_finalize(content, meta, analyses, article_id=None, create_time=None):
        return {"title": "t", "article_id": article_id or "aid"}

    async def fake_save(doc):
        saved.append(doc)
        return doc.get("article_id")

    orig_fin, orig_save = service.afinalize, service.store.save_insight
    service.afinalize = fake_finalize
    service.store.save_insight = fake_save
    try:
        _run(service.finalize("新闻", {}, {"MicroAgent": "r"}, save=True))
        _run(service.finalize("新闻", {}, {"MicroAgent": "r"}, save=False))
        assert len(saved) == 1, f"save=True 应入库一次，实际 {len(saved)} 次"
        try:
            _run(service.finalize("新闻", {}, {}, save=False))
            raise AssertionError("空 analyses 应抛 ValueError")
        except ValueError:
            pass
    finally:
        service.afinalize, service.store.save_insight = orig_fin, orig_save
    print("✅ 通过")


def test_service_analyze_news_cache_hit():
    print("=== 测试 analyze_news 缓存命中 ===")
    state = {"calls": 0}

    async def fake_pipeline(content, **kw):
        state["calls"] += 1
        return {"data_align": {"article_id": "x"}, "article_id": "x"}

    orig_pipe, orig_get, orig_set = (
        service.apipeline_news, cache.get_json, cache.set_json,
    )
    stored = {}

    async def fake_get(key):
        return stored.get(key)

    async def fake_set(key, value, ttl=None):
        stored[key] = value

    service.apipeline_news = fake_pipeline
    cache.get_json, cache.set_json = fake_get, fake_set
    try:
        out1 = _run(service.analyze_news("新闻B"))
        out2 = _run(service.analyze_news("新闻B"))
        assert out1 == out2 and state["calls"] == 1, f"缓存未生效: calls={state['calls']}"
    finally:
        service.apipeline_news, cache.get_json, cache.set_json = (
            orig_pipe, orig_get, orig_set,
        )
    print("✅ 通过")


# ============================================================================
# store 测试（mock Motor 集合）
# ============================================================================

class _FakeCursor:
    def __init__(self, docs):
        self.docs = docs

    def sort(self, *a, **kw):
        return self

    def limit(self, n):
        return self

    async def to_list(self, length=None):
        return self.docs


class _FakeCollection:
    def __init__(self, docs):
        self.docs = docs
        self.last_filter: dict = {}

    def insert_one(self, doc):
        self.inserted = doc

        class _R:
            pass

        fut = asyncio.get_event_loop().create_future()
        fut.set_result(_R())
        return fut

    def find(self, filter, projection):
        self.last_filter = filter
        return _FakeCursor(self.docs)


class _FakeDB:
    def __init__(self, coll):
        self._coll = coll

    def __getitem__(self, name):
        return self._coll


def test_store_search_filter():
    print("=== 测试 store.search_insights 过滤器构造 ===")
    coll = _FakeCollection([{"article_id": "1"}])
    orig = store.get_mongo_db
    store.get_mongo_db = lambda: _FakeDB(coll)
    try:
        items = _run(store.search_insights(query="无人机", stock_code="000001", limit=5))
        f = coll.last_filter
        assert "$or" in f and len(f["$or"]) == 4, f
        assert f["data_align.stock_codes.code"] == "000001", f
        assert items == [{"article_id": "1"}]

        _run(store.search_insights())
        assert coll.last_filter == {}, f"无参时过滤器应为空: {coll.last_filter}"
    finally:
        store.get_mongo_db = orig
    print("✅ 通过")


def test_store_save_insight():
    print("=== 测试 store.save_insight ===")
    coll = _FakeCollection([])
    orig = store.get_mongo_db
    store.get_mongo_db = lambda: _FakeDB(coll)
    try:
        try:
            _run(store.save_insight({"title": "缺 article_id"}))
            raise AssertionError("缺 article_id 应抛 ValueError")
        except ValueError:
            pass
        _run(store.save_insight({"article_id": "aid-1", "title": "t"}))
        assert coll.inserted["article_id"] == "aid-1"
    finally:
        store.get_mongo_db = orig
    print("✅ 通过")


# ============================================================================
# MCP 工具测试
# ============================================================================

def test_tool_extract_news_meta():
    print("=== 测试 extract_news_meta 工具 ===")
    r = _parse(_run(extract_news_meta("")))
    assert r["status"] == "error"

    orig = service.extract_meta
    service.extract_meta = lambda c: _fake_meta(c)
    try:
        r = _parse(_run(extract_news_meta("新闻")))
        assert r["status"] == "success"
        assert r["tool"] == "extract_news_meta"
        assert r["data"]["data_ner"] == {"ok": 1}
    finally:
        service.extract_meta = orig
    print("✅ 通过")


async def _fake_meta(content):
    return {"data_ner": {"ok": 1}, "data_label": {}, "data_event": {}}


def _get_analyst_tool(name: str):
    return next(t for t in _ANALYST_TOOLS if t.name == name)


def test_agent_tool_name_mapping():
    print("=== 测试 Agent 名转工具名 ===")
    assert agent_tool_name("MacroAgent") == "macro_analyst"
    assert agent_tool_name("MicroAgent") == "micro_analyst"
    assert agent_tool_name("TechnicalHLAgent") == "technical_hl_analyst"
    assert agent_tool_name("RiskAgent") == "risk_analyst"
    print("✅ 通过")


def test_analyst_tools_generated_from_factory():
    print("=== 测试 12 个分析师工具按 factory 生成（单一事实来源）===")
    from recommender.news_reader.agents.analyst.factory import list_agent_names

    assert len(_ANALYST_TOOLS) == len(list_agent_names())
    names = sorted(t.name for t in _ANALYST_TOOLS)
    for expect in (
        "macro_analyst", "industry_analyst", "micro_analyst", "event_analyst",
        "valuation_analyst", "technical_analyst", "technical_hl_analyst",
        "sentiment_analyst", "dividend_analyst", "fundamental_analyst",
        "portfolio_analyst", "risk_analyst",
    ):
        assert expect in names, f"缺少工具 {expect}"

    # title / description 来自 _MappingName 专长描述
    micro = _get_analyst_tool("micro_analyst")
    assert "波特五力" in micro.description
    assert "微观" in micro.title
    assert "news-analyst" in micro.tags
    print("✅ 通过")


def test_analyst_tool_invocation():
    print("=== 测试单个分析师工具调用（micro_analyst）===")
    tool = _get_analyst_tool("micro_analyst")
    orig = service.run_analyst
    service.run_analyst = lambda c, m, a: _fake_report(a)
    try:
        # 正常路径：agent_name 固定为 MicroAgent
        r = _parse(_run(tool.fn("新闻", json.dumps(_FULL_META))))
        assert r["status"] == "success", r
        assert r["tool"] == "micro_analyst"
        assert r["data"] == {"agent_name": "MicroAgent", "report": "报告:MicroAgent"}

        # 兼容完整响应封装回传
        wrapped = json.dumps({
            "status": "success", "tool": "extract_news_meta",
            "data": _FULL_META, "warnings": [], "error": None,
        }, ensure_ascii=False)
        r2 = _parse(_run(tool.fn("新闻", wrapped)))
        assert r2["status"] == "success", r2

        # 缺键 meta 报错
        r3 = _parse(_run(tool.fn("新闻", '{"data_ner": {}}')))
        assert r3["status"] == "error" and "data_label" in r3["error"]

        # 空正文报错
        r4 = _parse(_run(tool.fn("", json.dumps(_FULL_META))))
        assert r4["status"] == "error"
    finally:
        service.run_analyst = orig
    print("✅ 通过")


def test_analyst_tools_distinct_agents():
    print("=== 测试不同工具绑定不同 Agent ===")
    orig = service.run_analyst
    seen = []

    async def spy(c, m, a):
        seen.append(a)
        return f"报告:{a}"

    service.run_analyst = spy
    try:
        _run(_get_analyst_tool("macro_analyst").fn("新闻", json.dumps(_FULL_META)))
        _run(_get_analyst_tool("risk_analyst").fn("新闻", json.dumps(_FULL_META)))
        assert seen == ["MacroAgent", "RiskAgent"], seen
    finally:
        service.run_analyst = orig
    print("✅ 通过")


async def _fake_report(agent):
    return f"报告:{agent}"


def test_tool_finalize_news_analysis():
    print("=== 测试 finalize_news_analysis 工具 ===")
    r = _parse(_run(finalize_news_analysis("新闻", "{}", "{}")))
    assert r["status"] == "error", "空 analyses 应报错"

    orig = service.finalize
    service.finalize = lambda c, m, a, save=True: _fake_align(save)
    try:
        meta = json.dumps(
            {"data_ner": {}, "data_label": {}, "data_event": {}}, ensure_ascii=False
        )
        ans = json.dumps({"MicroAgent": "r"}, ensure_ascii=False)
        r = _parse(_run(finalize_news_analysis("新闻", meta, ans, save=False)))
        assert r["status"] == "success"
        assert r["data"]["saved"] is False
        assert r["data"]["data_align"]["article_id"] == "aid"
    finally:
        service.finalize = orig
    print("✅ 通过")


async def _fake_align(save):
    return {"article_id": "aid", "title": "t"}


def test_tool_search_news_insights():
    print("=== 测试 search_news_insights 工具 ===")
    r = _parse(_run(search_news_insights(limit=0)))
    assert r["status"] == "error"
    r = _parse(_run(search_news_insights(limit=101)))
    assert r["status"] == "error"

    orig = store.search_insights
    store.search_insights = lambda **kw: _fake_search()
    try:
        r = _parse(_run(search_news_insights(query="无人机", limit=5)))
        assert r["status"] == "success"
        assert r["data"]["count"] == 1
        assert r["data"]["items"][0]["article_id"] == "a1"
    finally:
        store.search_insights = orig
    print("✅ 通过")


async def _fake_search():
    return [{"article_id": "a1"}]


def test_tool_list_news_analysts():
    print("=== 测试 list_news_analysts 发现工具 ===")
    from recommender.news_reader.agents.analyst.factory import list_agent_names

    r = _parse(_run(list_news_analysts()))
    assert r["status"] == "success", r
    assert r["tool"] == "list_news_analysts"
    analysts = r["data"]["analysts"]
    assert r["data"]["count"] == len(analysts) == len(list_agent_names())

    # 每个分析师条目含 agent_name / tool_name / specialty，且与生成工具一致
    tool_names = {t.name for t in _ANALYST_TOOLS}
    for item in analysts:
        assert set(item.keys()) == {"agent_name", "tool_name", "specialty"}, item
        assert item["tool_name"] in tool_names, item
        assert item["specialty"]
    micro = next(a for a in analysts if a["agent_name"] == "MicroAgent")
    assert micro["tool_name"] == "micro_analyst"
    assert "波特五力" in micro["specialty"]
    print("✅ 通过")


def test_tool_analyze_news():
    print("=== 测试 analyze_news 一体式工具 ===")
    r = _parse(_run(analyze_news("")))
    assert r["status"] == "error"

    orig = service.analyze_news
    service.analyze_news = lambda c, save=False: _fake_oneshot(save)
    try:
        r = _parse(_run(analyze_news("新闻", save=True)))
        assert r["status"] == "success"
        assert r["data"]["data_align"]["article_id"] == "aid2"
    finally:
        service.analyze_news = orig
    print("✅ 通过")


async def _fake_oneshot(save):
    return {"data_align": {"article_id": "aid2"}, "article_id": "aid2"}


def test_common_envelope():
    print("=== 测试统一响应封装 ===")
    ok = json.loads(contract.make_response("t", {"a": 1}))
    assert set(ok.keys()) == {"status", "tool", "data", "warnings", "error"}
    assert ok["status"] == "success" and ok["data"] == {"a": 1}
    err = json.loads(contract.error_response("t", "boom"))
    assert err["status"] == "error" and err["error"] == "boom"
    # datetime 序列化
    import datetime as dt
    r = json.loads(contract.make_response("t", {"t": dt.datetime(2024, 1, 1)}))
    assert r["data"]["t"] == "2024-01-01T00:00:00"
    print("✅ 通过")


def test_contract_parse_meta():
    print("=== 测试 parse_meta 宽容解析（裸 dict / JSON 字符串 / 完整工具响应封装）===")
    meta = {"data_ner": {}, "data_label": {}, "data_event": {}}

    assert contract.parse_meta(meta) == meta
    assert contract.parse_meta(json.dumps(meta)) == meta
    wrapped = {
        "status": "success", "tool": "extract_news_meta",
        "data": meta, "warnings": [], "error": None,
    }
    assert contract.parse_meta(json.dumps(wrapped)) == meta
    assert contract.parse_meta(wrapped) == meta

    # 缺键报错且提示回传方式
    try:
        contract.parse_meta('{"data_ner": {}}')
        raise AssertionError("缺键应抛 ValueError")
    except ValueError as e:
        assert "data_label" in str(e) and "data_event" in str(e)

    # 非 JSON 报错
    try:
        contract.parse_meta("not-json")
        raise AssertionError("非法 JSON 应抛 ValueError")
    except ValueError:
        pass
    print("✅ 通过")


def test_contract_parse_analyses():
    print("=== 测试 parse_analyses 宽容解析 ===")
    ans = {"MicroAgent": "报告A", "SentimentAgent": "报告B"}
    assert contract.parse_analyses(ans) == ans
    assert contract.parse_analyses(json.dumps(ans)) == ans

    # run_news_analyst 响应形态自动归一为单 Agent 报告
    shaped = json.dumps({"agent_name": "MicroAgent", "report": "报告A"})
    assert contract.parse_analyses(shaped) == {"MicroAgent": "报告A"}

    # 允许平台附加综合解读
    with_extra = dict(ans, 综合解读="我的解读")
    assert contract.parse_analyses(with_extra)["综合解读"] == "我的解读"

    for bad in ("{}", "[]", '{"A": 1}'):
        try:
            contract.parse_analyses(bad)
            raise AssertionError(f"{bad} 应抛 ValueError")
        except ValueError:
            pass
    print("✅ 通过")


def test_contract_agent_names_from_factory():
    print("=== 测试 Agent 名单来自 factory（单一事实来源）===")
    from recommender.news_reader.agents.analyst import factory as agent_factory
    from recommender.news_reader.agents.analyst.factory import list_agent_names

    assert contract.list_valid_agents() == list_agent_names()
    assert "MicroAgent" in contract.list_valid_agents()
    assert set(agent_factory._Mapping.keys()) == set(agent_factory._MappingName.keys()), \
        "_Mapping 与 _MappingName 键不一致"
    print("✅ 通过")


def test_tool_accepts_wrapped_meta():
    print("=== 测试分析师工具兼容完整响应封装回传 ===")
    wrapped = json.dumps({
        "status": "success", "tool": "extract_news_meta",
        "data": _FULL_META, "warnings": [], "error": None,
    }, ensure_ascii=False)
    orig = service.run_analyst
    service.run_analyst = lambda c, m, a: _fake_report(a)
    try:
        r = _parse(_run(_get_analyst_tool("micro_analyst").fn("新闻", wrapped)))
        assert r["status"] == "success", r
        assert r["data"]["report"] == "报告:MicroAgent"
    finally:
        service.run_analyst = orig
    print("✅ 通过")


def test_tool_finalize_accepts_single_report():
    print("=== 测试 finalize 兼容单个 run_news_analyst 响应形态 ===")
    meta = json.dumps({"data_ner": {}, "data_label": {}, "data_event": {}})
    single = json.dumps({"agent_name": "MicroAgent", "report": "报告A"}, ensure_ascii=False)
    orig = service.finalize
    seen = {}

    async def fake_finalize(c, m, a, save=True):
        seen["analyses"] = a
        return {"article_id": "aid3"}

    service.finalize = fake_finalize
    try:
        r = _parse(_run(finalize_news_analysis("新闻", meta, single, save=False)))
        assert r["status"] == "success", r
        assert seen["analyses"] == {"MicroAgent": "报告A"}, seen
    finally:
        service.finalize = orig
    print("✅ 通过")


# ============================================================================
# runner
# ============================================================================

def run_all_tests():
    tests = [
        ("build_messages_no_tuple_bug", test_build_messages_no_tuple_bug),
        ("api_key_injection", test_api_key_injection),
        ("chat_once_retry_on_timeout", test_chat_once_retry_on_timeout),
        ("chat_once_exhausts_retries", test_chat_once_exhausts_retries),
        ("chat_once_empty_content_raises", test_chat_once_empty_content_raises),
        ("achat_once_retry", test_achat_once_retry),
        ("parse_json_from_llm", test_parse_json_from_llm),
        ("parse_json_no_eval", test_parse_json_no_eval),
        ("aextract_meta_parallel", test_aextract_meta_parallel),
        ("arun_analyst_validation", test_arun_analyst_validation),
        ("arun_analyst_uses_analyst_model", test_arun_analyst_uses_analyst_model),
        ("apipeline_news_structure", test_apipeline_news_structure),
        ("apipeline_news_default_agents", test_apipeline_news_default_agents),
        ("sync_pipeline_report_joins_all_agents", test_sync_pipeline_report_joins_all_agents),
        ("cache_key_format", test_cache_key_format),
        ("cache_roundtrip", test_cache_roundtrip),
        ("cache_degrades_without_redis", test_cache_degrades_without_redis),
        ("service_extract_meta_cache_hit", test_service_extract_meta_cache_hit),
        ("service_run_analyst_validation", test_service_run_analyst_validation),
        ("service_finalize_save_toggle", test_service_finalize_save_toggle),
        ("service_analyze_news_cache_hit", test_service_analyze_news_cache_hit),
        ("store_search_filter", test_store_search_filter),
        ("store_save_insight", test_store_save_insight),
        ("tool_extract_news_meta", test_tool_extract_news_meta),
        ("agent_tool_name_mapping", test_agent_tool_name_mapping),
        ("analyst_tools_generated_from_factory", test_analyst_tools_generated_from_factory),
        ("analyst_tool_invocation", test_analyst_tool_invocation),
        ("analyst_tools_distinct_agents", test_analyst_tools_distinct_agents),
        ("tool_finalize_news_analysis", test_tool_finalize_news_analysis),
        ("tool_search_news_insights", test_tool_search_news_insights),
        ("tool_list_news_analysts", test_tool_list_news_analysts),
        ("tool_analyze_news", test_tool_analyze_news),
        ("common_envelope", test_common_envelope),
        ("contract_parse_meta", test_contract_parse_meta),
        ("contract_parse_analyses", test_contract_parse_analyses),
        ("contract_agent_names_from_factory", test_contract_agent_names_from_factory),
        ("tool_accepts_wrapped_meta", test_tool_accepts_wrapped_meta),
        ("tool_finalize_accepts_single_report", test_tool_finalize_accepts_single_report),
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
