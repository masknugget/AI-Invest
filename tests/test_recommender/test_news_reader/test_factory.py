# -*- coding: utf-8 -*-
"""
news_reader agents factory 测试：create_analyst / list_agent_names / 映射一致性。

运行方式：
    python tests/test_recommender/test_news_reader/test_factory.py
"""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

from recommender.news_reader.agents.analyst import factory


def test_list_agent_names():
    print("=== 测试 list_agent_names 返回全部 Agent ===")
    names = factory.list_agent_names()
    assert len(names) == len(factory._Mapping) > 0
    for expect in ("MacroAgent", "MicroAgent", "SentimentAgent", "RiskAgent"):
        assert expect in names, f"缺少 {expect}"
    # 返回副本，外部修改不影响内部映射
    names.append("FakeAgent")
    assert "FakeAgent" not in factory.list_agent_names()
    print(f"共 {len(factory._Mapping)} 个 Agent")
    print("✅ 通过")


def test_create_analyst_valid():
    print("=== 测试 create_analyst 合法 Agent ===")
    for name in factory.list_agent_names():
        prompt, display = factory.create_analyst(name)
        assert isinstance(prompt, str) and len(prompt) > 50, f"{name} prompt 异常"
        assert isinstance(display, str) and display, f"{name} 显示名为空"
    # 抽样验证专长描述内容
    _, macro_display = factory.create_analyst("MacroAgent")
    assert "宏观" in macro_display
    print("✅ 通过")


def test_create_analyst_unknown():
    print("=== 测试 create_analyst 未知 Agent 返回空 ===")
    prompt, display = factory.create_analyst("NoSuchAgent")
    assert prompt == "" and display == ""
    print("✅ 通过")


def test_mapping_consistency():
    print("=== 测试 _Mapping 与 _MappingName 键一致（防漂移）===")
    assert set(factory._Mapping.keys()) == set(factory._MappingName.keys()), (
        f"_Mapping 独有: {set(factory._Mapping) - set(factory._MappingName)}; "
        f"_MappingName 独有: {set(factory._MappingName) - set(factory._Mapping)}"
    )
    # 每个中文描述非空且与 Agent 数一致
    for name, desc in factory._MappingName.items():
        assert desc.strip(), f"{name} 描述为空"
    print("✅ 通过")


def run_all_tests():
    tests = [
        ("list_agent_names", test_list_agent_names),
        ("create_analyst_valid", test_create_analyst_valid),
        ("create_analyst_unknown", test_create_analyst_unknown),
        ("mapping_consistency", test_mapping_consistency),
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
