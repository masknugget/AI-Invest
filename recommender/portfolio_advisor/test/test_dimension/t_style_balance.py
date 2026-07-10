"""
style_balance.py 中的估值得分与风格桶分配测试（普通 Python 脚本，无需 pytest）。

验证：在没有 peTTM / pbMRQ / psTTM / pcfNcfTTM 字段时，
_compute_value_score 返回中性得分，且 _assign_style_buckets 不会报错。

运行方式：
    python recommender/portfolio_advisor/test/test_dimension/t_style_balance.py
"""

import os
import sys

sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        )
    ),
)

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "style_balance", "recommender/portfolio_advisor/dimension/style_balance.py"
)
_style_balance = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_style_balance)

import pandas as pd


def test_compute_value_score_without_value_fields():
    """DataFrame 没有估值字段时，_compute_value_score 返回中性 0.5。"""
    df = pd.DataFrame({
        "code": ["A", "B", "C", "D", "E"],
        "close": [10.0, 20.0, 30.0, 40.0, 50.0],
    })
    value_score = _style_balance._compute_value_score(df)

    assert len(value_score) == len(df)
    assert all(score == 0.5 for score in value_score)
    print("  [OK] test_compute_value_score_without_value_fields 通过")


def test_assign_style_buckets_with_constant_value_score():
    """估值得分恒定时，风格桶不会报错，且所有 value 标签为 blend。"""
    size_score = pd.Series([0.1, 0.3, 0.5, 0.7, 0.9])
    value_score = pd.Series([0.5, 0.5, 0.5, 0.5, 0.5])

    buckets = _style_balance._assign_style_buckets(size_score, value_score, n_buckets=3)

    assert len(buckets) == len(size_score)
    for bucket in buckets:
        assert bucket.endswith("_blend")
    print("  [OK] test_assign_style_buckets_with_constant_value_score 通过")


def run_all_tests():
    """运行所有测试。"""
    tests = [
        ("compute_value_score_without_value_fields", test_compute_value_score_without_value_fields),
        ("assign_style_buckets_with_constant_value_score", test_assign_style_buckets_with_constant_value_score),
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
