# -*- coding: utf-8 -*-
"""
news_reader.utils 测试：parse_json_from_llm / gen_uuid。

重点回归：eval() 兜底已移除，恶意输入不会被执行。

运行方式：
    python tests/test_recommender/test_news_reader/test_utils.py
"""
import json
import re
import sys
import uuid
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

from langchain_core.exceptions import OutputParserException

from recommender.news_reader.utils import gen_uuid, parse_json_from_llm


def test_gen_uuid():
    print("=== 测试 gen_uuid 生成合法 UUID4 ===")
    u = gen_uuid()
    parsed = uuid.UUID(u)
    assert parsed.version == 4, u
    assert str(parsed) == u
    # 两次生成不重复
    assert gen_uuid() != gen_uuid()
    print("✅ 通过")


def test_parse_plain_and_fenced_json():
    print("=== 测试解析普通 JSON 与 ```json 代码块 ===")
    assert parse_json_from_llm('{"a": 1, "b": [1, 2]}') == {"a": 1, "b": [1, 2]}
    assert parse_json_from_llm('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_from_llm("说明文字 ```json\n{\"a\": 1}\n``` 结尾") == {"a": 1}
    print("✅ 通过")


def test_parse_repaired_json():
    print("=== 测试轻微损坏 JSON 的修复解析 ===")
    # 单引号 / 尾逗号等常见 LLM 输出瑕疵
    assert parse_json_from_llm("{'a': 1}") == {"a": 1}
    assert parse_json_from_llm('{"a": 1,}') == {"a": 1}
    # json_repair 激进修复：残缺花括号也能兜出结果（不抛异常）
    assert parse_json_from_llm("{broken") == ["broken"]
    print("✅ 通过")


def test_parse_invalid_raises_no_eval():
    print("=== 测试非法输入抛 OutputParserException 且 eval 兜底已移除 ===")
    for bad in ("完全不是 JSON", "123abc"):
        try:
            parse_json_from_llm(bad)
            raise AssertionError(f"{bad!r} 应抛 OutputParserException")
        except OutputParserException:
            pass

    # 恶意输入：若 eval 兜底存在则会被执行
    marker = []
    payload = f"__import__('builtins').exec({marker!r}.append(1))"
    try:
        parse_json_from_llm(payload)
    except Exception:
        pass
    assert not marker, "eval 兜底仍存在：恶意输入被执行"
    print("✅ 通过")


def run_all_tests():
    tests = [
        ("gen_uuid", test_gen_uuid),
        ("parse_plain_and_fenced_json", test_parse_plain_and_fenced_json),
        ("parse_repaired_json", test_parse_repaired_json),
        ("parse_invalid_raises_no_eval", test_parse_invalid_raises_no_eval),
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
