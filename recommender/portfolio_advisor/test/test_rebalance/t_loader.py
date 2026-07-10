"""
候选股票池加载器测试

测试 recommender.portfolio_advisor.rebalance.loader 中的加载函数
"""
import importlib.util
import os
import sys
import tempfile
import types as py_types
import warnings
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd


# ============================================================
# 构造最小存根模块，避免触发 recommender/__init__.py 的依赖链
# ============================================================
@dataclass
class _StockCandidate:
    code: str
    df: pd.DataFrame
    dimension_scores: dict = field(default_factory=dict)
    industry: Optional[str] = None


@dataclass
class _CandidatePool:
    candidates: list = field(default_factory=list)

    def __len__(self):
        return len(self.candidates)


_types_stub = py_types.ModuleType("recommender.portfolio_advisor.rebalance.types")
setattr(_types_stub, "StockCandidate", _StockCandidate)
setattr(_types_stub, "CandidatePool", _CandidatePool)
sys.modules["recommender.portfolio_advisor.rebalance.types"] = _types_stub


_utils_stub = py_types.ModuleType("recommender.portfolio_advisor.utils")


def _load_jsonl(path):
    """最小 JSONL 读取实现，仅用于测试。"""
    import json

    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


setattr(_utils_stub, "load_jsonl", _load_jsonl)
sys.modules["recommender.portfolio_advisor.utils"] = _utils_stub


# 直接加载目标模块
_project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)
_module_path = os.path.join(_project_root, "recommender", "portfolio_advisor", "rebalance", "loader.py")
_spec = importlib.util.spec_from_file_location("rebalance_loader", _module_path)
assert _spec is not None and _spec.loader is not None, f"无法加载模块: {_module_path}"
loader = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(loader)

load_candidate_pool_from_jsonl = loader.load_candidate_pool_from_jsonl
load_candidate_pool_from_jsonl_as_pool = loader.load_candidate_pool_from_jsonl_as_pool
_extract_dimension_scores = loader._extract_dimension_scores
_load_df_for_code = loader._load_df_for_code


# ============================================================
# 测试辅助
# ============================================================
def _make_df(dates, code="000001"):
    """构造一个模拟行情 DataFrame。"""
    return pd.DataFrame({"date": dates, "close": list(range(len(dates))), "code": code})


class _FakeDataSet:
    """模拟 FileVisitor.data_set() 返回对象。"""

    def __init__(self, data_map):
        self._data = data_map

    def get(self, code):
        return self._data.get(code)


class _FakeFileVisitor:
    """模拟 FileVisitor 对象。"""

    def __init__(self, data_map):
        self._data_map = data_map

    def data_set(self):
        return _FakeDataSet(self._data_map)


def _write_jsonl(path, records):
    """将记录写入 JSONL 文件。"""
    import json

    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


# ============================================================
# 测试用例
# ============================================================
def test_extract_dimension_scores():
    """测试五维得分提取"""
    print("\n=== 测试 _extract_dimension_scores ===")

    record = {
        "code": "000001",
        "drawdown_control": 0.8,
        "portfolio_diversification": 0.7,
        "position_efficiency": 0.9,
        "return_stability": 0.6,
        "style_balance": 0.75,
        "other_field": "ignored",
    }
    scores = _extract_dimension_scores(record)

    expected_dims = {
        "drawdown_control",
        "portfolio_diversification",
        "position_efficiency",
        "return_stability",
        "style_balance",
    }
    assert set(scores.keys()) == expected_dims, f"维度集合不匹配: {scores.keys()}"
    assert scores["drawdown_control"] == 0.8
    assert scores["position_efficiency"] == 0.9
    assert "other_field" not in scores

    print("[PASS] 五维得分提取正确")
    return True


def test_load_df_for_code_with_visitor():
    """测试传入 file_visitor 时拉取行情"""
    print("\n=== 测试 _load_df_for_code 使用外部 visitor ===")

    df = _make_df(["2024-01-01", "2024-01-02"], code="000001")
    visitor = _FakeFileVisitor({"000001": df})
    result = _load_df_for_code("000001", file_visitor=visitor.data_set())

    assert result is not None
    assert result.equals(df), "返回的 DataFrame 应与输入一致"
    print("[PASS] 使用外部 visitor 正确拉取行情")
    return True


def test_load_df_for_code_missing_data():
    """测试无数据时返回 None"""
    print("\n=== 测试 _load_df_for_code 无数据返回 None ===")

    visitor = _FakeFileVisitor({})
    result = _load_df_for_code("000001", file_visitor=visitor.data_set())
    assert result is None, "无数据时应返回 None"

    print("[PASS] 无数据时正确返回 None")
    return True


def test_load_candidate_pool_from_jsonl_basic():
    """测试从 JSONL 正常加载候选池"""
    print("\n=== 测试 load_candidate_pool_from_jsonl 基本情况 ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "candidates.jsonl")
        records = [
            {
                "code": "000001",
                "drawdown_control": 0.8,
                "portfolio_diversification": 0.7,
                "position_efficiency": 0.9,
                "return_stability": 0.6,
                "style_balance": 0.75,
            },
            {
                "code": "000002",
                "drawdown_control": 0.5,
                "portfolio_diversification": 0.6,
                "position_efficiency": 0.7,
                "return_stability": 0.8,
                "style_balance": 0.65,
            },
        ]
        _write_jsonl(path, records)

        df1 = _make_df(["2024-01-01", "2024-01-02"], code="000001")
        df2 = _make_df(["2024-01-01", "2024-01-02"], code="000002")
        visitor = _FakeFileVisitor({"000001": df1, "000002": df2})

        candidates = load_candidate_pool_from_jsonl(path, file_visitor=visitor.data_set())

    assert len(candidates) == 2, f"应加载 2 条候选，实际 {len(candidates)}"
    assert candidates[0].code == "000001"
    assert candidates[1].code == "000002"
    assert candidates[0].dimension_scores["drawdown_control"] == 0.8
    assert candidates[1].df.equals(df2)

    print("[PASS] 正常加载候选池")
    return True


def test_load_candidate_pool_from_jsonl_missing_code_required():
    """测试 require_code=True 时缺少 code 字段抛出 ValueError"""
    print("\n=== 测试 require_code=True 缺少 code ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "candidates.jsonl")
        records = [
            {"drawdown_control": 0.8},
        ]
        _write_jsonl(path, records)

        try:
            load_candidate_pool_from_jsonl(path, require_code=True)
            assert False, "应抛出 ValueError"
        except ValueError as e:
            assert "缺少 'code' 字段" in str(e)
            print(f"[PASS] 正确抛出 ValueError: {e}")

    return True


def test_load_candidate_pool_from_jsonl_missing_code_optional():
    """测试 require_code=False 时跳过缺少 code 的记录"""
    print("\n=== 测试 require_code=False 缺少 code ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "candidates.jsonl")
        records = [
            {"drawdown_control": 0.8},
            {
                "code": "000001",
                "drawdown_control": 0.8,
                "portfolio_diversification": 0.7,
                "position_efficiency": 0.9,
                "return_stability": 0.6,
                "style_balance": 0.75,
            },
        ]
        _write_jsonl(path, records)

        df1 = _make_df(["2024-01-01", "2024-01-02"], code="000001")
        visitor = _FakeFileVisitor({"000001": df1})

        candidates = load_candidate_pool_from_jsonl(path, require_code=False, file_visitor=visitor.data_set())

    assert len(candidates) == 1, f"应跳过第一条，只加载 1 条，实际 {len(candidates)}"
    assert candidates[0].code == "000001"

    print("[PASS] 可选 code 时正确跳过缺失记录")
    return True


def test_load_candidate_pool_from_jsonl_skip_no_data():
    """测试无法拉取行情时跳过并告警"""
    print("\n=== 测试无法拉取行情时跳过 ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "candidates.jsonl")
        records = [
            {
                "code": "000001",
                "drawdown_control": 0.8,
            },
            {
                "code": "000002",
                "drawdown_control": 0.5,
            },
        ]
        _write_jsonl(path, records)

        # 只为 000002 提供数据
        df2 = _make_df(["2024-01-01"], code="000002")
        visitor = _FakeFileVisitor({"000002": df2})

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            candidates = load_candidate_pool_from_jsonl(path, file_visitor=visitor.data_set())

    assert len(candidates) == 1, f"应跳过无数据的 000001，实际 {len(candidates)}"
    assert candidates[0].code == "000002"
    assert len(w) >= 1, "应触发至少一次警告"
    assert any("无法为股票 000001 拉取完整行情" in str(warning.message) for warning in w)

    print("[PASS] 无数据时正确跳过并告警")
    return True


def test_load_candidate_pool_from_jsonl_no_fetch():
    """测试 fetch_full_df=False 时加载候选但不拉取行情 df。"""
    print("\n=== 测试 fetch_full_df=False ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "candidates.jsonl")
        records = [
            {
                "code": "000001",
                "drawdown_control": 0.8,
            },
        ]
        _write_jsonl(path, records)

        candidates = load_candidate_pool_from_jsonl(path, fetch_full_df=False)

    assert len(candidates) == 1, "fetch_full_df=False 时仍应加载候选"
    assert candidates[0].df is None
    print("[PASS] fetch_full_df=False 时正确加载候选（df 为 None）")
    return True


def test_load_candidate_pool_from_jsonl_limit():
    """测试 limit 限制加载数量"""
    print("\n=== 测试 limit 限制 ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "candidates.jsonl")
        records = [
            {"code": f"{i:06d}", "drawdown_control": 0.5} for i in range(1, 6)
        ]
        _write_jsonl(path, records)

        data_map = {r["code"]: _make_df(["2024-01-01"], code=r["code"]) for r in records}
        visitor = _FakeFileVisitor(data_map)

        candidates = load_candidate_pool_from_jsonl(path, file_visitor=visitor.data_set(), limit=2)

    assert len(candidates) == 2, f"limit=2 时应加载 2 条，实际 {len(candidates)}"
    assert candidates[0].code == "000001"
    assert candidates[1].code == "000002"

    print("[PASS] limit 正确限制加载数量")
    return True


def test_load_candidate_pool_from_jsonl_as_pool():
    """测试以 CandidatePool 形式返回"""
    print("\n=== 测试 load_candidate_pool_from_jsonl_as_pool ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "candidates.jsonl")
        records = [
            {
                "code": "000001",
                "drawdown_control": 0.8,
                "portfolio_diversification": 0.7,
                "position_efficiency": 0.9,
                "return_stability": 0.6,
                "style_balance": 0.75,
            },
        ]
        _write_jsonl(path, records)

        df1 = _make_df(["2024-01-01"], code="000001")
        visitor = _FakeFileVisitor({"000001": df1})

        pool = load_candidate_pool_from_jsonl_as_pool(path, file_visitor=visitor.data_set())

    assert isinstance(pool, _CandidatePool), "应返回 CandidatePool 对象"
    assert len(pool) == 1
    assert pool.candidates[0].code == "000001"

    print("[PASS] CandidatePool 形式返回正确")
    return True


# ============================================================
# 测试运行器
# ============================================================
def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("开始候选股票池加载器测试")
    print("=" * 60)

    tests = [
        ("_extract_dimension_scores", test_extract_dimension_scores),
        ("_load_df_for_code 使用外部 visitor", test_load_df_for_code_with_visitor),
        ("_load_df_for_code 无数据", test_load_df_for_code_missing_data),
        ("load_candidate_pool_from_jsonl 基本情况", test_load_candidate_pool_from_jsonl_basic),
        ("require_code=True 缺少 code", test_load_candidate_pool_from_jsonl_missing_code_required),
        ("require_code=False 缺少 code", test_load_candidate_pool_from_jsonl_missing_code_optional),
        ("无法拉取行情时跳过", test_load_candidate_pool_from_jsonl_skip_no_data),
        ("fetch_full_df=False", test_load_candidate_pool_from_jsonl_no_fetch),
        ("limit 限制", test_load_candidate_pool_from_jsonl_limit),
        ("load_candidate_pool_from_jsonl_as_pool", test_load_candidate_pool_from_jsonl_as_pool),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"\n[FAIL] {test_name} 测试失败: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"测试结果: 通过 {passed}, 失败 {failed}")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
