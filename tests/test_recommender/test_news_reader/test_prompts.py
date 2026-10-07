# -*- coding: utf-8 -*-
"""
news_reader prompt 构建函数测试：pipelines / analysts / report / align_data。

纯字符串断言（无 LLM 调用），按 factory 映射动态遍历 12 个分析师 prompt，
新增 Agent 时自动纳入覆盖。

运行方式：
    python tests/test_recommender/test_news_reader/test_prompts.py
"""
import json
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

from recommender.news_reader.agents.analyst import factory as agent_factory
from recommender.news_reader.agents.pipelines.event import prompt_event
from recommender.news_reader.agents.pipelines.labels import prompt_labels
from recommender.news_reader.agents.pipelines.ner import prompt_ner
from recommender.news_reader.agents.pipelines.router import prompt_router
from recommender.news_reader.agents.report import prompt_report
from recommender.news_reader.agents.reporter.align_data import prompt_align_data


def _assert_prompt_shape(name: str, prompt: str):
    assert isinstance(prompt, str) and len(prompt) > 50, f"{name} prompt 过短或为空"
    assert "#" in prompt, f"{name} prompt 缺少结构标题"


def test_pipeline_prompts():
    print("=== 测试阶段1提取与路由 prompt ===")
    for name, fn in [
        ("ner", prompt_ner),
        ("labels", prompt_labels),
        ("event", prompt_event),
        ("router", prompt_router),
    ]:
        _assert_prompt_shape(name, fn())
    router = prompt_router()
    # router 中引用的每个 Agent 都必须是 factory 中的合法 Agent（无悬空引用）
    import re
    referenced = set(re.findall(r"([A-Z][A-Za-z]*Agent)", router))
    valid = set(agent_factory.list_agent_names())
    dangling = referenced - valid
    assert not dangling, f"router prompt 引用了不存在的 Agent: {dangling}"
    # 路由规则覆盖的核心 Agent
    for core in ("MacroAgent", "MicroAgent", "SentimentAgent", "RiskAgent"):
        assert core in router, f"router prompt 缺少 {core}"
    print(f"router 引用 {len(referenced)} 个 Agent，全部合法")
    print("✅ 通过")


def test_all_analyst_prompts():
    print("=== 测试 12 个分析师 prompt（动态遍历 factory）===")
    prompts = {}
    for agent_name in agent_factory.list_agent_names():
        prompt, display = agent_factory.create_analyst(agent_name)
        _assert_prompt_shape(agent_name, prompt)
        assert display and isinstance(display, str), f"{agent_name} 缺少中文显示名"
        prompts[agent_name] = prompt

    # 各分析师 prompt 应互不相同（不是复制粘贴的占位）
    unique = set(prompts.values())
    assert len(unique) == len(prompts), "存在重复的分析师 prompt"
    print(f"共 {len(prompts)} 个分析师 prompt，全部独立")
    print("✅ 通过")


def test_report_and_align_prompts():
    print("=== 测试综合报告与结构化对齐 prompt ===")
    report = prompt_report()
    _assert_prompt_shape("report", report)
    assert "财经" in report

    sample = {"data_report": "x", "MicroAgent": "y", "data_ner": {}}
    align = prompt_align_data(json.dumps(sample, ensure_ascii=False))
    _assert_prompt_shape("align_data", align)
    # 输入数据被序列化拼入
    assert '"data_ner"' in align
    # 输出 schema 关键字段（article_id/create_time 由 afinalize 代码注入，不在 prompt schema 内）
    for field in ("title", "stock_codes", "metadata"):
        assert field in align, f"align schema 缺少 {field}"
    print("✅ 通过")


def run_all_tests():
    tests = [
        ("pipeline_prompts", test_pipeline_prompts),
        ("all_analyst_prompts", test_all_analyst_prompts),
        ("report_and_align_prompts", test_report_and_align_prompts),
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
