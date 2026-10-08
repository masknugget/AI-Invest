"""
portfolio_advisor 工具函数测试（自定义 runner 模式，非 pytest）

覆盖：utils（jsonl / build_portfolio）、industry_distribution、data_read、qa

用法：
    python tests/test_recommender/test_portfolio_advisor/test_utils.py
"""
import sys
import tempfile
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

# Windows 控制台 GBK 无法输出 emoji，统一改为 UTF-8（与 app/__main__.py 一致）
if sys.platform == "win32" and sys.stdout.encoding != "utf-8":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from recommender.portfolio_advisor import data_read, qa, utils
from recommender.portfolio_advisor.industry_distribution import merge_and_sum_decimal

SCORES_PATH = (
    project_root / "recommender" / "portfolio_advisor" / "data" / "stock_dimension_scores.jsonl"
)


# ============================================================================
# utils: JSONL 读写
# ============================================================================

def test_save_load_jsonl_roundtrip():
    print("=== 测试 save_jsonl / load_jsonl 往返 ===")
    data = [{"code": "sh.600000", "name": "浦发银行"}, {"code": "sz.000001", "score": 88.5}]
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "sub" / "out.jsonl"  # 父目录不存在，应自动创建
        utils.save_jsonl(data, path)
        loaded = utils.load_jsonl(path)
    assert loaded == data, f"往返结果不一致: {loaded}"
    print("✅ 通过")


def test_load_jsonl_missing_file():
    print("=== 测试 load_jsonl 文件不存在 ===")
    try:
        utils.load_jsonl("/nonexistent/path/x.jsonl")
    except FileNotFoundError:
        print("✅ 通过（抛出 FileNotFoundError）")
    else:
        raise AssertionError("文件不存在时应抛出 FileNotFoundError")


def test_load_jsonl_skips_blank_lines():
    print("=== 测试 load_jsonl 跳过空行 ===")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "x.jsonl"
        path.write_text('{"a": 1}\n\n   \n{"a": 2}\n', encoding="utf-8")
        loaded = utils.load_jsonl(path)
    assert loaded == [{"a": 1}, {"a": 2}], loaded
    print("✅ 通过")


# ============================================================================
# utils: build_portfolio
# ============================================================================

def _dedup_dates(df):
    """fixture parquet 存在少量重复日期（20/1372），build_portfolio 按 date 对齐前先去重。"""
    return df.drop_duplicates(subset="date", keep="last").reset_index(drop=True)


def test_build_portfolio_basic():
    print("=== 测试 build_portfolio 基本合成 ===")
    dfs = [_dedup_dates(data_read.df_1), _dedup_dates(data_read.df_2)]
    df = utils.build_portfolio(dfs, [0.5, 0.5], align="inner")
    assert df["code"].iloc[0] == "PORTFOLIO"
    assert len(df) > 0
    # 必要列应存在
    for col in ("date", "close", "pctChg"):
        assert col in df.columns, f"缺少列 {col}"
    # 权重归一化后 [2, 2] 与 [0.5, 0.5] 应等价
    df2 = utils.build_portfolio(dfs, [2.0, 2.0], align="inner")
    assert abs(float(df["close"].iloc[-1]) - float(df2["close"].iloc[-1])) < 1e-6
    print(f"inner 对齐行数: {len(df)}")
    print("✅ 通过")


def test_build_portfolio_align_modes():
    print("=== 测试 build_portfolio inner/outer 对齐 ===")
    dfs = [_dedup_dates(data_read.df_1), _dedup_dates(data_read.df_2)]
    inner = utils.build_portfolio(dfs, [0.5, 0.5], align="inner")
    outer = utils.build_portfolio(dfs, [0.5, 0.5], align="outer")
    assert len(outer) >= len(inner), "outer 并集行数应不少于 inner 交集"
    print(f"inner={len(inner)} 行, outer={len(outer)} 行")
    print("✅ 通过")


def test_build_portfolio_length_mismatch():
    print("=== 测试 build_portfolio 长度不一致 ===")
    try:
        utils.build_portfolio([data_read.df_1], [0.5, 0.5])
    except ValueError:
        print("✅ 通过（抛出 ValueError）")
    else:
        raise AssertionError("dfs 与 weights 长度不一致时应抛出 ValueError")


def test_value_error_instead_of_assert():
    print("=== 测试输入校验使用 ValueError（python -O 下 assert 会被剥离） ===")
    from recommender.portfolio_advisor.dimension.drawdown_control import (
        calculate_portfolio_mdd,
        normalize_mdd_to_score,
    )
    try:
        calculate_portfolio_mdd([data_read.df_1], [0.5])  # 权重和不为 1
    except ValueError:
        print("  MDD 权重和校验 -> ValueError ✅")
    else:
        raise AssertionError("权重和不为 1 应抛出 ValueError")
    try:
        normalize_mdd_to_score(-0.1)  # 负 MDD
    except ValueError:
        print("  负 MDD -> ValueError ✅")
    else:
        raise AssertionError("负 MDD 应抛出 ValueError")
    print("✅ 通过")


# ============================================================================
# industry_distribution
# ============================================================================

def test_merge_and_sum_decimal():
    print("=== 测试 merge_and_sum_decimal ===")
    merged = merge_and_sum_decimal([{"a": 0.1, "b": 1.0}, {"a": 0.2}])
    # Decimal 精度：0.1 + 0.2 应精确等于 0.3
    assert merged["a"] == 0.3, merged
    assert merged["b"] == 1.0
    assert merge_and_sum_decimal([]) == {}
    print(f"merged: {merged}")
    print("✅ 通过")


# ============================================================================
# data_read / qa
# ============================================================================

def test_data_read_load_all():
    print("=== 测试 data_read.load_all ===")
    data = data_read.load_all()
    assert len(data) == 5, f"应加载 5 个 parquet，实际 {len(data)}"
    for name, df in data.items():
        assert df is not None and not df.empty, f"{name} 为空"
        for col in ("date", "close", "pctChg", "code"):
            assert col in df.columns, f"{name} 缺少列 {col}"
    print(f"5 个 parquet 均有效，列: {list(data['df_1'].columns)}")
    print("✅ 通过")


def test_qa_faq_data():
    print("=== 测试 qa.faq 数据完整性 ===")
    assert isinstance(qa.faq, list) and len(qa.faq) > 0
    for i, item in enumerate(qa.faq):
        assert "q" in item and item["q"], f"第 {i} 条缺少问题"
        assert "anwser" in item and item["anwser"], f"第 {i} 条缺少答案"
    print(f"共 {len(qa.faq)} 条 FAQ")
    print("✅ 通过")


# ============================================================================
# runner
# ============================================================================

def test_parse_risks_always_returns_list():
    print("=== 测试 parse_risks 始终返回列表 ===")
    from recommender.portfolio_advisor.analyst import parse_risks

    # 正常 JSON 列表
    risks = parse_risks('[{"summary": "s", "detail": "d"}]')
    assert risks == [{"summary": "s", "detail": "d"}], risks
    # ```json 包裹
    risks = parse_risks('```json\n[{"summary": "s", "detail": "d"}]\n```')
    assert len(risks) == 1, risks
    # 非列表输出（单个 dict）：旧实现直接返回 dict，现统一为 []
    risks = parse_risks('{"summary": "s", "detail": "d"}')
    assert risks == [], f"非列表输出应返回空列表，实际 {risks!r}"
    # 非法 JSON / 空输入
    assert parse_risks("not json") == []
    assert parse_risks(None) == []
    assert parse_risks("") == []
    print("✅ 通过")


def run_all_tests():
    tests = [
        ("jsonl_roundtrip", test_save_load_jsonl_roundtrip),
        ("jsonl_missing_file", test_load_jsonl_missing_file),
        ("jsonl_blank_lines", test_load_jsonl_skips_blank_lines),
        ("build_portfolio_basic", test_build_portfolio_basic),
        ("build_portfolio_align", test_build_portfolio_align_modes),
        ("build_portfolio_length_mismatch", test_build_portfolio_length_mismatch),
        ("value_error_not_assert", test_value_error_instead_of_assert),
        ("merge_and_sum_decimal", test_merge_and_sum_decimal),
        ("data_read_load_all", test_data_read_load_all),
        ("qa_faq_data", test_qa_faq_data),
        ("parse_risks", test_parse_risks_always_returns_list),
    ]
    passed = failed = 0
    for name, func in tests:
        try:
            func()
            passed += 1
        except Exception as e:
            print(f"❌ {name} failed: {e}")
            failed += 1
        print("-" * 60)
    print(f"[test_utils] 结果: {passed} 通过, {failed} 失败")
    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if run_all_tests() else 1)
