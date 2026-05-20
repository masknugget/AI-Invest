"""
用户画像生成模块测试
测试 build_user_profile_prompt, _infer_category 等核心逻辑

运行方式:
    python tests/test_recommender/test_gen_user_profiles.py
"""
import os
import sys
import json

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# 直接导入目标模块，避免触发 recommender/__init__.py 中的依赖链
import importlib.util
spec = importlib.util.spec_from_file_location(
    "gen_user_profiles",
    os.path.join(project_root, "recommender", "user_profile", "gen_user_profiles.py")
)
gen_user_profiles = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen_user_profiles)

build_user_profile_prompt = gen_user_profiles.build_user_profile_prompt
_infer_category = gen_user_profiles._infer_category


# ==================== 测试数据 ====================

SAMPLE_INSIGHT_WITH_LABELS = {
    "content": "AI Sector Rebounds: Strategic Partnerships Drive Growth",
    "data_label": {
        "topics": ["AI", "Technology"],
        "sectors": ["Technology", "Semiconductor"],
        "keywords": ["AI", "partnerships", "growth"]
    },
    "data_report": "Strong earnings drive semiconductor stocks to new highs...",
}

SAMPLE_INSIGHT_NO_LABELS = {
    "content": "Fed signals higher for longer rate stance",
    "data_label": {},
}

SAMPLE_INSIGHT_INVALID_LABELS = {
    "content": "Market sentiment improves amid earnings season",
    "data_label": None,
}

SAMPLE_USER_DATA = {
    "recent_news_browsing_7d": [
        {
            "title": "How is the war with Iran impacting interest rates",
            "summary": "Middle East Conflict: Market Pivot...",
            "category": "Macro & Micro",
            "dwellSec": 185,
            "timestamp": "2026-05-10T08:15:00Z",
        },
        {
            "title": "AI Sector Rebounds: Strategic Partnerships Drive 2026 Q2",
            "summary": "NVIDIA and Microsoft lead the charge...",
            "category": "Sector",
            "dwellSec": 95,
            "timestamp": "2026-05-11T09:20:00Z",
        },
    ],
    "clickstream_7d": [],
    "search_logs_30d": [],
    "trade_history_30d": [],
    "watchlist_snapshot": [],
    "content_engagement_14d": [],
}


# ==================== 测试函数 ====================

def test_infer_category_with_topics():
    """测试 _infer_category：从 topics 提取分类"""
    print("=== 测试 _infer_category（含 topics）===")

    result = _infer_category(SAMPLE_INSIGHT_WITH_LABELS)

    assert result == "AI", f"期望 'AI'，实际 '{result}'"
    print(f"[PASS] 从 topics 提取: '{result}'")
    return True


def test_infer_category_with_sectors():
    """测试 _infer_category：从 sectors 提取分类（无 topics）"""
    print("\n=== 测试 _infer_category（含 sectors，无 topics）===")

    insight = {
        "content": "Test",
        "data_label": {
            "sectors": ["Finance", "Banking"],
        }
    }
    result = _infer_category(insight)

    assert result == "Finance", f"期望 'Finance'，实际 '{result}'"
    print(f"[PASS] 从 sectors 提取: '{result}'")
    return True


def test_infer_category_no_labels():
    """测试 _infer_category：无标签时返回 General"""
    print("\n=== 测试 _infer_category（无标签）===")

    result = _infer_category(SAMPLE_INSIGHT_NO_LABELS)

    assert result == "General", f"期望 'General'，实际 '{result}'"
    print(f"[PASS] 无标签时默认: '{result}'")
    return True


def test_infer_category_invalid_labels():
    """测试 _infer_category：无效标签时返回 General"""
    print("\n=== 测试 _infer_category（无效标签）===")

    result = _infer_category(SAMPLE_INSIGHT_INVALID_LABELS)

    assert result == "General", f"期望 'General'，实际 '{result}'"
    print(f"[PASS] 无效标签时默认: '{result}'")
    return True


def test_build_prompt_structure():
    """测试 build_user_profile_prompt：返回结构完整性"""
    print("\n=== 测试 build_user_profile_prompt（结构检查）===")

    result = build_user_profile_prompt(
        user_data=SAMPLE_USER_DATA,
        market_context="Test market context",
        include_few_shot=False,
    )

    assert "system" in result, "结果应包含 'system' 字段"
    assert "user" in result, "结果应包含 'user' 字段"
    assert "meta" in result, "结果应包含 'meta' 字段"
    assert isinstance(result["system"], str), "system 应为字符串"
    assert isinstance(result["user"], str), "user 应为字符串"
    assert isinstance(result["meta"], dict), "meta 应为字典"

    print(f"[PASS] 返回结构完整")
    print(f"       system 长度: {len(result['system'])} 字符")
    print(f"       user 长度: {len(result['user'])} 字符")
    print(f"       meta: {result['meta']}")
    return True


def test_build_prompt_contains_user_data():
    """测试 build_user_profile_prompt：user prompt 包含输入数据"""
    print("\n=== 测试 build_user_profile_prompt（数据注入）===")

    result = build_user_profile_prompt(
        user_data=SAMPLE_USER_DATA,
        include_few_shot=False,
    )

    user_prompt = result["user"]

    # 检查用户数据被注入
    assert "recent_news_browsing_7d" in user_prompt, "user prompt 应包含数据字段名"
    assert "AI Sector Rebounds" in user_prompt, "user prompt 应包含新闻标题"
    assert "Test market context" not in user_prompt or "market_context" in user_prompt, "应包含市场环境"

    print(f"[PASS] 数据正确注入到 prompt")
    return True


def test_build_prompt_meta_fields():
    """测试 build_user_profile_prompt：meta 字段内容"""
    print("\n=== 测试 build_user_profile_prompt（meta 字段）===")

    result = build_user_profile_prompt(
        user_data=SAMPLE_USER_DATA,
        model_version="test-v1.0",
        include_few_shot=False,
    )

    meta = result["meta"]

    assert "input_hash" in meta, "meta 应包含 input_hash"
    assert "current_time" in meta, "meta 应包含 current_time"
    assert "model_version" in meta, "meta 应包含 model_version"
    assert meta["model_version"] == "test-v1.0", "model_version 应匹配"
    assert meta["few_shot_included"] == False, "few_shot_included 应为 False"
    assert len(meta["input_hash"]) == 8, "input_hash 应为 8 位"

    print(f"[PASS] meta 字段完整")
    print(f"       input_hash: {meta['input_hash']}")
    print(f"       model_version: {meta['model_version']}")
    return True


def test_build_prompt_system_content():
    """测试 build_user_profile_prompt：system prompt 内容检查"""
    print("\n=== 测试 build_user_profile_prompt（system 内容）===")

    result = build_user_profile_prompt(
        user_data=SAMPLE_USER_DATA,
        include_few_shot=False,
    )

    system = result["system"]

    # 检查关键内容存在
    assert "# Role" in system, "system 应包含 Role 部分"
    assert "# Core Mission" in system, "system 应包含 Core Mission"
    assert "# Tag Taxonomy" in system, "system 应包含 Tag Taxonomy"
    assert "# Output Schema" in system, "system 应包含 Output Schema"
    assert "generatedTags" in system, "system 应提及 generatedTags"
    assert "MOMENTUM_TRADER" in system, "system 应包含交易风格标签"
    assert "POLICY_REGULATION_WATCHER" in system, "system 应包含新闻关注焦点标签"

    print(f"[PASS] system prompt 内容完整")
    print(f"       包含 Role, Core Mission, Tag Taxonomy, Output Schema")
    return True


def test_build_prompt_with_few_shot():
    """测试 build_user_profile_prompt：启用 few-shot"""
    print("\n=== 测试 build_user_profile_prompt（启用 few-shot）===")

    result_with = build_user_profile_prompt(
        user_data=SAMPLE_USER_DATA,
        include_few_shot=True,
    )

    result_without = build_user_profile_prompt(
        user_data=SAMPLE_USER_DATA,
        include_few_shot=False,
    )

    # 启用 few-shot 后 system 应更长
    assert len(result_with["system"]) > len(result_without["system"]), \
        "启用 few-shot 后 system 应更长"

    # 检查 few-shot 示例存在
    assert "Few-Shot Example" in result_with["system"] or "输入示例" in result_with["system"], \
        "启用 few-shot 后应包含示例"

    print(f"[PASS] few-shot 模式正确")
    print(f"       启用 few-shot: {len(result_with['system'])} 字符")
    print(f"       禁用 few-shot: {len(result_without['system'])} 字符")
    return True


def test_build_prompt_json_output_schema():
    """测试 build_user_profile_prompt：JSON 输出格式要求"""
    print("\n=== 测试 build_user_profile_prompt（JSON Schema）===")

    result = build_user_profile_prompt(
        user_data=SAMPLE_USER_DATA,
        include_few_shot=False,
    )

    system = result["system"]

    # 检查输出格式要求
    assert '"generatedTags"' in system, "应要求 generatedTags 字段"
    assert '"summary"' in system, "应要求 summary 字段"
    assert '"audit"' in system, "应要求 audit 字段"
    assert '"confidence"' in system, "应要求 confidence 字段"
    assert '"evidence"' in system, "应要求 evidence 字段"
    assert '"expiresAt"' in system, "应要求 expiresAt 字段"

    print(f"[PASS] JSON 输出 schema 完整")
    return True


# ==================== 测试运行器 ====================

def run_all_tests():
    """运行所有测试"""
    tests = [
        ("_infer_category（含 topics）", test_infer_category_with_topics),
        ("_infer_category（含 sectors）", test_infer_category_with_sectors),
        ("_infer_category（无标签）", test_infer_category_no_labels),
        ("_infer_category（无效标签）", test_infer_category_invalid_labels),
        ("build_prompt（结构检查）", test_build_prompt_structure),
        ("build_prompt（数据注入）", test_build_prompt_contains_user_data),
        ("build_prompt（meta 字段）", test_build_prompt_meta_fields),
        ("build_prompt（system 内容）", test_build_prompt_system_content),
        ("build_prompt（few-shot）", test_build_prompt_with_few_shot),
        ("build_prompt（JSON Schema）", test_build_prompt_json_output_schema),
    ]

    passed = 0
    failed = 0

    print("=" * 60)
    print("用户画像生成模块测试")
    print("=" * 60)

    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"\n❌ {test_name} 测试失败: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"测试结果: 通过 {passed}, 失败 {failed}")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
