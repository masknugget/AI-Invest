# -*- coding: utf-8 -*-
"""
news_reader.consumer.news 流水线测试：同步 / 异步 / 阶段函数 / 并发与限流。

LLM 调用全部 mock（替换 consumer 模块的 chat_once / achat_once），
不依赖网络、API key、MongoDB、Redis。

运行方式：
    python tests/test_recommender/test_news_reader/test_consumer.py
"""
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict

project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

import recommender.news_reader.consumer.news as consumer

_FULL_META = {"data_ner": {}, "data_label": {}, "data_event": {}}
_ROUTER_JSON = '{"routing_plan": {"primary_agents": [{"agent": "MicroAgent"}, {"agent": "SentimentAgent"}]}}'


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _make_fake_achat(state: Dict[str, Any], sleep=0.02):
    async def fake(prompt, sys_prompt=None, model=None):
        state["current"] += 1
        state["max"] = max(state["max"], state["current"])
        state["calls"] += 1
        state.setdefault("models", []).append(model)
        if sleep:
            await asyncio.sleep(sleep)
        state["current"] -= 1
        return '{"ok": true}'

    return fake


# ============================================================================
# 阶段级异步函数
# ============================================================================

def test_aextract_meta_parallel():
    print("=== 测试 aextract_meta 三路并行 ===")
    state = {"current": 0, "max": 0, "calls": 0}
    orig = consumer.achat_once
    consumer.achat_once = _make_fake_achat(state)
    try:
        meta = _run(consumer.aextract_meta("某公司发布财报"))
    finally:
        consumer.achat_once = orig
    assert state["calls"] == 3, state
    assert state["max"] == 3, f"应三路并发，max={state['max']}"
    assert all(k in meta for k in _FULL_META), meta.keys()
    print("✅ 通过")


def test_build_p_data():
    print("=== 测试 build_p_data 拼接 meta ===")
    p_data = consumer.build_p_data("新闻正文", {"data_ner": {"e": 1}})
    assert "新闻正文" in p_data
    # meta 各阶段结果被序列化拼入对应小节
    assert "# ner" in p_data and '"e": 1' in p_data
    assert "# label" in p_data and "# event" in p_data
    print("✅ 通过")


def test_arun_analyst():
    print("=== 测试 arun_analyst 单 Agent 与非法名 ===")
    state: Dict[str, Any] = {"current": 0, "max": 0, "calls": 0}
    orig = consumer.achat_once
    consumer.achat_once = _make_fake_achat(state)
    try:
        report = _run(consumer.arun_analyst("新闻", _FULL_META, "MicroAgent"))
        assert report == '{"ok": true}'
        assert state["calls"] == 1
        # 分析 Agent 使用 ANALYST 模型槽位（无 env 时与默认一致，但参数应显式传入）
        assert state["models"][-1] is not None

        try:
            _run(consumer.arun_analyst("新闻", _FULL_META, "NoSuchAgent"))
            raise AssertionError("非法 Agent 应抛 ValueError")
        except ValueError as e:
            assert "NoSuchAgent" in str(e)
    finally:
        consumer.achat_once = orig
    print("✅ 通过")


def test_arun_analysts_semaphore():
    print("=== 测试 arun_analysts 并发上限（MAX_PARALLEL_AGENTS）===")
    state = {"current": 0, "max": 0, "calls": 0}
    orig = consumer.achat_once
    consumer.achat_once = _make_fake_achat(state, sleep=0.02)
    try:
        agents = ["MacroAgent", "IndustryAgent", "MicroAgent", "EventAgent",
                  "ValuationAgent", "SentimentAgent"]  # 6 个 > 上限 4
        results = _run(consumer.arun_analysts("新闻", _FULL_META, agents))
        assert set(results.keys()) == set(agents)
        assert state["calls"] == 6
        assert 2 <= state["max"] <= consumer.MAX_PARALLEL_AGENTS, state
    finally:
        consumer.achat_once = orig
    print(f"max 并发: {state['max']}（上限 {consumer.MAX_PARALLEL_AGENTS}）")
    print("✅ 通过")


def test_aroute_agents():
    print("=== 测试 aroute_agents 解析路由结果 ===")
    async def fake(prompt, sys_prompt=None, model=None):
        return _ROUTER_JSON

    orig = consumer.achat_once
    consumer.achat_once = fake
    try:
        agents = _run(consumer.aroute_agents("新闻", _FULL_META))
        assert agents == ["MicroAgent", "SentimentAgent"], agents
    finally:
        consumer.achat_once = orig
    print("✅ 通过")


def test_afinalize():
    print("=== 测试 afinalize 注入 article_id / create_time ===")
    state = {"calls": 0}

    async def fake(prompt, sys_prompt=None, model=None):
        state["calls"] += 1
        return '{"title": "t"}'

    orig = consumer.achat_once
    consumer.achat_once = fake
    try:
        align = _run(consumer.afinalize("新闻", _FULL_META, {"MicroAgent": "r"}))
        assert align["title"] == "t"
        assert align["article_id"] and align["create_time"]
        assert state["calls"] == 1
    finally:
        consumer.achat_once = orig
    print("✅ 通过")


# ============================================================================
# 异步一体式流水线
# ============================================================================

def test_apipeline_news_with_agents():
    print("=== 测试 apipeline_news 指定 Agent 并行执行 ===")
    state = {"current": 0, "max": 0, "calls": 0}
    orig = consumer.achat_once
    consumer.achat_once = _make_fake_achat(state)
    try:
        out = _run(consumer.apipeline_news(
            "新闻", agent_names=["MicroAgent", "SentimentAgent"], with_report=False
        ))
    finally:
        consumer.achat_once = orig
    for k in ("data_ner", "data_label", "data_event", "MicroAgent", "SentimentAgent",
              "data_align", "article_id", "content"):
        assert k in out, f"缺少 {k}"
    assert state["max"] >= 2, state
    assert "data_report" not in out
    print("✅ 通过")


def test_apipeline_news_with_router_and_report():
    print("=== 测试 apipeline_news 服务端路由 + 综合报告 ===")
    state = {"current": 0, "max": 0, "calls": 0, "report_prompt": None}

    async def fake(prompt, sys_prompt=None, model=None):
        state["calls"] += 1
        state["current"] += 1
        state["max"] = max(state["max"], state["current"])
        await asyncio.sleep(0.01)
        state["current"] -= 1
        if "路由决策专家" in prompt:
            return _ROUTER_JSON
        if "财经新闻与分析写作" in prompt:
            state["report_prompt"] = prompt
            return "综合报告"
        return '{"ok": true}'

    orig = consumer.achat_once
    consumer.achat_once = fake
    try:
        out = _run(consumer.apipeline_news("新闻", agent_names=None, with_router=True, with_report=True))
    finally:
        consumer.achat_once = orig
    assert out["data_report"] == "综合报告"
    # 路由选中 2 个 Agent → 报告输入应包含全部 Agent 输出（content[0] bug 回归）
    # 注：异步流水线 content 块以 agent_name 为键（同步流水线用中文显示名）
    rp = state["report_prompt"] or ""
    assert "#MicroAgent" in rp and "#SentimentAgent" in rp
    print("✅ 通过")


def test_apipeline_news_router_empty_fallback():
    print("=== 测试路由为空时走默认 Agent ===")
    async def fake(prompt, sys_prompt=None, model=None):
        return '{"routing_plan": {"primary_agents": []}}'

    orig = consumer.achat_once
    consumer.achat_once = fake
    try:
        out = _run(consumer.apipeline_news("新闻", agent_names=None, with_router=True))
        assert "data_align" in out
    finally:
        consumer.achat_once = orig
    print("✅ 通过")


# ============================================================================
# 同步一体式流水线（兼容 dev.py 旧调用）
# ============================================================================

def test_pipeline_news_sync():
    print("=== 测试同步 pipeline_news 全流程（报告拼接 bug 回归）===")
    captured = {}

    def fake_chat(prompt, sys_prompt=None, model=None):
        if "财经新闻与分析写作" in prompt:
            captured["report_prompt"] = prompt
            return "报告"
        if "路由决策专家" in prompt:
            return _ROUTER_JSON
        if "金融数据结构化工程师" in prompt:
            return '{"title": "t"}'
        return '{"ok": true}'

    orig = consumer.chat_once
    consumer.chat_once = fake_chat
    try:
        out = consumer.pipeline_news("新闻")
    finally:
        consumer.chat_once = orig

    for k in ("data_ner", "data_label", "data_event", "data_router",
              "data_report", "data_align", "article_id", "content"):
        assert k in out, f"缺少 {k}"
    rp = captured.get("report_prompt", "")
    assert "公司微观分析" in rp, "报告输入缺少 MicroAgent 结果"
    assert "情绪与资金流向分析" in rp, "报告输入缺少 SentimentAgent 结果"
    assert out["data_align"]["article_id"] == out["article_id"]
    print("✅ 通过")


def run_all_tests():
    tests = [
        ("aextract_meta_parallel", test_aextract_meta_parallel),
        ("build_p_data", test_build_p_data),
        ("arun_analyst", test_arun_analyst),
        ("arun_analysts_semaphore", test_arun_analysts_semaphore),
        ("aroute_agents", test_aroute_agents),
        ("afinalize", test_afinalize),
        ("apipeline_news_with_agents", test_apipeline_news_with_agents),
        ("apipeline_news_with_router_and_report", test_apipeline_news_with_router_and_report),
        ("apipeline_news_router_empty_fallback", test_apipeline_news_router_empty_fallback),
        ("pipeline_news_sync", test_pipeline_news_sync),
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
