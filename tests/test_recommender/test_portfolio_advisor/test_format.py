"""
portfolio_advisor 结果格式化测试（自定义 runner 模式，非 pytest）

覆盖：format_adapt（dimensions / report / risk_alerts / rebalance / stress）
上游结果由 dimension / rebalance / stress 模块真实计算得出。

用法：
    python tests/test_recommender/test_portfolio_advisor/test_format.py
"""
import json
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

if sys.platform == "win32" and sys.stdout.encoding != "utf-8":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from recommender.portfolio_advisor.data_read import load_all
from recommender.portfolio_advisor.dimension.run import (
    compute_portfolio_dimensions,
    load_random_portfolio,
)
from recommender.portfolio_advisor.format_adapt.format_advisor import (
    format_advisor_result,
    format_dimensions,
    format_report,
    format_risk_alerts,
)
from recommender.portfolio_advisor.format_adapt.format_rebalance import (
    format_rebalance_plans,
)
from recommender.portfolio_advisor.format_adapt.format_stress import (
    format_all_stress_reports,
)
from recommender.portfolio_advisor.rebalance import suggest_rebalance
from recommender.portfolio_advisor.rebalance.loader import load_stock_scores_from_jsonl
from recommender.portfolio_advisor.stress_portfolio.history_stress import (
    compute_historical_stress,
)
from recommender.portfolio_advisor.stress_portfolio.scenario_stress import (
    compute_scenario_stress,
)
from recommender.portfolio_advisor.stress_portfolio.sector_stress import (
    compute_sector_stress,
)

SCORES_PATH = str(
    project_root / "recommender" / "portfolio_advisor" / "data" / "stock_dimension_scores.jsonl"
)
_FIXTURE_DFS = load_all()
CODES = [str(df["code"].iloc[0]) for df in _FIXTURE_DFS.values()]
PORTFOLIO = [{"code": c, "weight": 0.2} for c in CODES]
_INDUSTRY = {"sz.300005": "计算机", "sz.300291": "计算机", "sh.601689": "汽车",
             "sz.300237": "医药生物", "sz.300121": "电子"}
INDUSTRY_LOOKUP = lambda code: _INDUSTRY.get(code)  # noqa: E731


def _first_codes(n: int):
    codes = []
    with open(SCORES_PATH, encoding="utf-8") as f:
        for line in f:
            codes.append(json.loads(line)["code"])
            if len(codes) >= n:
                break
    return codes


def _equal_weights(n: int):
    w = [round(1.0 / n, 4)] * n
    w[-1] = round(1.0 - sum(w[:-1]), 4)
    return w


# ============================================================================
# dimensions / report / risk_alerts
# ============================================================================

def test_format_dimensions():
    print("=== 测试 format_dimensions ===")
    result = compute_portfolio_dimensions(load_random_portfolio(5), [0.2] * 5)
    formatted = format_dimensions(result)
    assert "dimensions" in formatted, "应包含 dimensions 字段"
    items = formatted["dimensions"]
    assert len(items) == 5, f"应有 5 个维度，实际 {len(items)}"
    for item in items:
        for key in ("key", "name", "score", "weight", "description"):
            assert key in item, f"维度项缺少字段 {key}"
        assert 0 <= item["score"] <= 100
    # 输出应可被 JSON 序列化（前端可直接使用）
    json.dumps(formatted, ensure_ascii=False)
    print(f"5 个维度: {[i['name'] for i in items]}")
    print("✅ 通过")


def test_format_report():
    print("=== 测试 format_report ===")
    result = compute_portfolio_dimensions(load_random_portfolio(5), [0.2] * 5)
    report = format_report(result, comprehensive_str="综合诊断文本", update_time="2026-10-08")
    for key in ("health_score", "rating", "comment", "update_time", "disclaimer"):
        assert key in report, f"报告缺少字段 {key}"
    assert 0 <= report["health_score"] <= 100
    assert report["update_time"] == "2026-10-08"
    print(f"健康分: {report['health_score']}")
    print("✅ 通过")


def test_format_risk_alerts():
    print("=== 测试 format_risk_alerts ===")
    risks = [{"summary": "行业集中度过高", "detail": "第一大行业占比超过 50%"},
             {"summary": "组合波动偏大", "detail": "年化波动率高于基准"}]
    alerts = format_risk_alerts(risks)
    assert "alerts" in alerts and "total_count" in alerts
    assert alerts["total_count"] == 2
    for item in alerts["alerts"]:
        for key in ("id", "severity", "title", "description", "icon"):
            assert key in item, f"风险项缺少字段 {key}"
        assert item["severity"] in ("low", "medium", "high")
    json.dumps(alerts, ensure_ascii=False)
    print(f"风险项: {[a['title'] for a in alerts['alerts']]}")
    print("✅ 通过")


def test_format_advisor_result():
    print("=== 测试 format_advisor_result 汇总 ===")
    result = compute_portfolio_dimensions(load_random_portfolio(5), [0.2] * 5)
    dimensions = format_dimensions(result)
    report = format_report(result, comprehensive_str="综合诊断文本")
    alerts = format_risk_alerts([{"summary": "s", "detail": "d"}])
    combined = format_advisor_result(
        dimensions=dimensions,
        risk_report=report,
        risk_alert=alerts,
        industry_distribution={"计算机": 0.4, "电子": 0.2},
    )
    assert "dimensions" in combined and "risk_report" in combined
    assert "risk_alert" in combined and "industry_distribution" in combined
    json.dumps(combined, ensure_ascii=False)
    print("✅ 通过")


# ============================================================================
# rebalance 格式化
# ============================================================================

def test_format_rebalance_plans():
    print("=== 测试 format_rebalance_plans ===")
    codes = _first_codes(4)
    plans = suggest_rebalance(codes, _equal_weights(4), SCORES_PATH, max_actions=1, top_k=2)
    all_scores = load_stock_scores_from_jsonl(SCORES_PATH)
    formatted = format_rebalance_plans(
        plans, all_scores, current_codes=codes, current_weights=_equal_weights(4),
        include_llm_reason=False,  # 本机未配置 LLM key，跳过理由文本生成
    )
    assert isinstance(formatted, list) and len(formatted) == len(plans)
    for plan in formatted:
        for key in ("score_before", "score_after", "improvement", "actions"):
            assert key in plan, f"方案缺少字段 {key}"
        for action in plan["actions"]:
            assert "code_in" in action and "code_out" in action
            assert "weight_in" in action and "reason" in action
    json.dumps(formatted, ensure_ascii=False)
    print(f"格式化 {len(formatted)} 个方案")
    print("✅ 通过")


# ============================================================================
# stress 格式化
# ============================================================================

def test_format_all_stress_reports():
    print("=== 测试 format_all_stress_reports ===")
    dfs_map = dict(zip(CODES, _FIXTURE_DFS.values()))
    hist = compute_historical_stress(PORTFOLIO, dfs_map)
    macro = [compute_scenario_stress(PORTFOLIO, name, industry_lookup=INDUSTRY_LOOKUP)
             for name in ("美联储加息", "通胀上行")]
    sector = [compute_sector_stress(PORTFOLIO, sector="科技", sector_callback_pct=0.20,
                                    industry_lookup=INDUSTRY_LOOKUP)]

    combined = format_all_stress_reports(hist, macro, sector)
    # 返回结构：{"stress": {...}, "macro": {...}, "sector": {...}}，每组含 title + scenarios
    for group in ("stress", "macro", "sector"):
        assert group in combined, f"缺少 {group} 结果"
        assert "title" in combined[group] and len(combined[group]["scenarios"]) > 0
    json.dumps(combined, ensure_ascii=False)
    print(f"历史 {len(combined['stress']['scenarios'])} / 宏观 {len(combined['macro']['scenarios'])} / "
          f"行业 {len(combined['sector']['scenarios'])}")
    print("✅ 通过")


def run_all_tests():
    tests = [
        ("format_dimensions", test_format_dimensions),
        ("format_report", test_format_report),
        ("format_risk_alerts", test_format_risk_alerts),
        ("format_advisor_result", test_format_advisor_result),
        ("format_rebalance_plans", test_format_rebalance_plans),
        ("format_all_stress_reports", test_format_all_stress_reports),
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
    print(f"[test_format] 结果: {passed} 通过, {failed} 失败")
    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if run_all_tests() else 1)
