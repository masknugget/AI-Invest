"""
调仓理由生成测试（普通 Python 脚本，无需 pytest）。

覆盖 recommender.portfolio_advisor.rebalance.reason 中的 reason_llm：
- 正确构建 prompt 并调用 chat_once
- 正确返回 LLM 结果

运行方式：
    python recommender/portfolio_advisor/test/test_rebalance/t_reason.py
"""

import importlib.util
import os
import sys
import types

# 添加项目根目录到路径
sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        )
    ),
)

# mock news_reader.llms，避免加载真实 LLM 依赖
if "recommender.news_reader.llms" not in sys.modules:
    _llms_mock = types.ModuleType("recommender.news_reader.llms")
    _captured_prompts: list = []

    def _fake_chat_once(prompt: str) -> str:
        """记录 prompt 并返回固定结果。"""
        _captured_prompts.append(prompt)
        return '{"reason": "测试理由"}'

    setattr(_llms_mock, "chat_once", _fake_chat_once)
    sys.modules["recommender.news_reader.llms"] = _llms_mock

# 直接加载目标模块，避免触发其他依赖链
_project_root = os.path.dirname(
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
)
_module_path = os.path.join(_project_root, "recommender", "portfolio_advisor", "rebalance", "reason.py")
_spec = importlib.util.spec_from_file_location("rebalance_reason", _module_path)
assert _spec is not None and _spec.loader is not None, f"无法加载模块: {_module_path}"
reason = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(reason)

reason_llm = reason.reason_llm


def _last_prompt() -> str:
    """获取最近一次调用 chat_once 的 prompt。"""
    assert len(_captured_prompts) > 0, "chat_once 未被调用"
    return _captured_prompts[-1]


def test_reason_llm_calls_chat_once():
    """reason_llm 调用 chat_once 并返回其结果。"""
    _captured_prompts.clear()

    result = reason_llm(
        code_in="000001",
        dimension_in="低估值，PE 5 倍",
        code_out="000002",
        dimension_out="高估值，PE 50 倍",
    )

    assert len(_captured_prompts) == 1
    assert result == '{"reason": "测试理由"}'
    print("  [OK] test_reason_llm_calls_chat_once 通过")


def test_reason_llm_prompt_contains_inputs():
    """prompt 中包含调入调出代码和维度信息。"""
    _captured_prompts.clear()

    reason_llm(
        code_in="000001",
        dimension_in="调入维度描述",
        code_out="000002",
        dimension_out="调出维度描述",
    )

    prompt = _last_prompt()
    assert "000001" in prompt
    assert "000002" in prompt
    assert "调入维度描述" in prompt
    assert "调出维度描述" in prompt
    print("  [OK] test_reason_llm_prompt_contains_inputs 通过")


def test_reason_llm_prompt_contains_task_and_format():
    """prompt 中包含任务说明和 JSON 输出格式要求。"""
    _captured_prompts.clear()

    reason_llm(
        code_in="A",
        dimension_in="dim_a",
        code_out="B",
        dimension_out="dim_b",
    )

    prompt = _last_prompt()
    assert "股票调仓" in prompt
    assert "json" in prompt.lower()
    assert '"reason"' in prompt
    assert "## 调入" in prompt
    assert "## 调出" in prompt
    print("  [OK] test_reason_llm_prompt_contains_task_and_format 通过")


def test_reason_llm_return_value_passthrough():
    """reason_llm 原样返回 chat_once 的输出。"""
    _captured_prompts.clear()

    # 临时替换 reason 模块中的 chat_once 以验证透传
    original_chat_once = getattr(reason, "chat_once")

    def custom_chat_once(_prompt: str) -> str:
        return "自定义 LLM 返回内容"

    try:
        setattr(reason, "chat_once", custom_chat_once)
        result = reason_llm(
            code_in="X",
            dimension_in="x_dim",
            code_out="Y",
            dimension_out="y_dim",
        )
        assert result == "自定义 LLM 返回内容"
    finally:
        setattr(reason, "chat_once", original_chat_once)

    print("  [OK] test_reason_llm_return_value_passthrough 通过")


def run_all_tests():
    """运行所有测试。"""
    tests = [
        ("reason_llm_calls_chat_once", test_reason_llm_calls_chat_once),
        ("reason_llm_prompt_contains_inputs", test_reason_llm_prompt_contains_inputs),
        ("reason_llm_prompt_contains_task_and_format", test_reason_llm_prompt_contains_task_and_format),
        ("reason_llm_return_value_passthrough", test_reason_llm_return_value_passthrough),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"\n  [FAIL] {test_name} 测试失败: {e}")
            failed += 1

    print(f"\n测试结果: 通过 {passed}, 失败 {failed}")
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
