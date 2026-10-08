"""
Portfolio Advisor MCP 工具测试（自定义 runner 模式，非 pytest）

用法：
    python tests/test_services/test_mcp/test_portfolio_advisor_mcp.py

说明：
- 五维评分 / 压力测试 / 全景报告需要行情数据，测试中用 fixture parquet
  （recommender/portfolio_advisor/data/df_*.parquet）monkeypatch 掉
  _common.fetch_quotes / fetch_quote_df，避免依赖网络与 MongoDB。
- 行业查询 monkeypatch 为固定映射。
- 调仓建议走真实 stock_dimension_scores.jsonl（本仓库自带 fixture）。
"""
import json
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

# Windows 控制台 GBK 无法输出 emoji，统一改为 UTF-8（与 app/__main__.py 一致）
if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import pandas as pd

from app.services.mcp.tools.portfolio_advice import data_source
from app.services.mcp.tools.portfolio_advice.diagnosis import portfolio_diagnosis
from app.services.mcp.tools.portfolio_advice.risk_alerts import portfolio_risk_alerts
from app.services.mcp.tools.portfolio_advice.rebalance import portfolio_rebalance_suggestion
from app.services.mcp.tools.portfolio_advice.stress_test import portfolio_stress_test
from app.services.mcp.tools.portfolio_advice.full_report import portfolio_full_report

# fixture 组合：data/df_1 ~ df_5
FIXTURE_CODES = ["sz.300005", "sz.300291", "sh.601689", "sz.300237", "sz.300121"]
FIXTURE_WEIGHTS = [0.2, 0.2, 0.2, 0.2, 0.2]

_FAKE_INDUSTRY = {
    "sz.300005": "计算机",
    "sz.300291": "计算机",
    "sh.601689": "汽车",
    "sz.300237": "医药生物",
    "sz.300121": "电子",
}


def _load_fixture_quotes(codes):
    """从 fixture parquet 构建行情 DataFrame；fixture 外的代码抛错。"""
    result = {}
    for code in codes:
        for i in range(1, 6):
            df = pd.read_parquet(
                project_root / "recommender" / "portfolio_advisor" / "data" / f"df_{i}.parquet"
            )
            if df["code"].iloc[0] == code:
                result[code] = df
                break
        else:
            raise ValueError(f"fixture 中不存在 {code} 的行情")
    return result


def _patch_data(monkeypatch_setter=None):
    """替换行情获取与行业查询为 fixture/固定实现（打点在 data_source 层）。"""
    data_source.fetch_quotes = _load_fixture_quotes
    data_source.industry_lookup = lambda code: _FAKE_INDUSTRY.get(code)
    data_source.build_industry_distribution = _build_dist_fixed


def _build_dist_fixed(codes, weights):
    dist = {}
    for c, w in zip(codes, weights):
        ind = _FAKE_INDUSTRY.get(c, "未知行业")
        dist[ind] = dist.get(ind, 0.0) + w
    return dist


def _parse(resp):
    assert isinstance(resp, str), "工具必须返回 JSON 字符串"
    return json.loads(resp)


# ============================================================================
# 测试用例
# ============================================================================

def test_diagnosis_normal():
    print("=== 测试 portfolio_diagnosis 正常路径 ===")
    data = _parse(portfolio_diagnosis(FIXTURE_CODES, FIXTURE_WEIGHTS))
    assert data["status"] == "success", data
    assert data["tool"] == "portfolio_diagnosis"
    for dim in ("drawdown_control", "portfolio_diversification", "position_efficiency",
                "return_stability", "style_balance"):
        assert "score" in data["data"][dim], f"{dim} 缺少 score"
    assert 0 <= data["data"]["composite_score"] <= 100
    assert abs(sum(data["data"]["dimension_weights"].values()) - 1.0) < 1e-6
    print(f"综合健康分: {data['data']['composite_score']:.2f}")
    print("✅ 通过")


def test_diagnosis_weight_auto_normalize():
    print("=== 测试权重自动归一化 ===")
    data = _parse(portfolio_diagnosis(FIXTURE_CODES, [2, 2, 2, 2, 2]))
    assert data["status"] == "success", data
    assert abs(sum(data["data"]["weights"]) - 1.0) < 1e-9
    print("✅ 通过")


def test_validate_errors():
    print("=== 测试参数校验错误路径 ===")
    cases = [
        (["sz.300005"], [0.5, 0.5], "长度不一致"),
        (["sz.300005", "sz.300005"], [0.5, 0.5], "重复代码"),
        (["sz.300005"], [-0.5], "负权重"),
        ([], [], "空列表"),
    ]
    for codes, weights, name in cases:
        data = _parse(portfolio_diagnosis(codes, weights))
        assert data["status"] == "error", f"{name} 应返回 error"
        assert data["error"], f"{name} 缺少错误信息"
        print(f"  {name}: {data['error']}")
    print("✅ 通过")


def test_risk_alerts():
    print("=== 测试 portfolio_risk_alerts ===")
    data = _parse(portfolio_risk_alerts(FIXTURE_CODES, [0.4, 0.2, 0.2, 0.1, 0.1]))
    assert data["status"] == "success", data
    assert "industry_hhi" in data["data"]
    assert "计算机" in data["data"]["industry_distribution"]
    assert all(r["source"] == "rule_based" for r in data["data"]["risk_items"])
    # 0.4 权重 + 40% 计算机集中度 -> 应触发规则项
    assert len(data["data"]["risk_items"]) >= 1
    print(f"HHI={data['data']['industry_hhi']:.2f}, 风险项: {[r['summary'] for r in data['data']['risk_items']]}")
    print("✅ 通过")


def test_stress_history():
    print("=== 测试 portfolio_stress_test（history） ===")
    data = _parse(portfolio_stress_test(FIXTURE_CODES, FIXTURE_WEIGHTS, scenario_type="history"))
    assert data["status"] in ("success", "partial"), data
    assert data["data"]["scenario_type"] == "history"
    assert len(data["data"]["results"]) > 0
    print(f"历史场景数: {len(data['data']['results'])}")
    print("✅ 通过")


def test_stress_scenario_and_sector():
    print("=== 测试 portfolio_stress_test（scenario/sector/非法类型） ===")
    for st in ("scenario", "sector"):
        data = _parse(portfolio_stress_test(FIXTURE_CODES, FIXTURE_WEIGHTS, scenario_type=st))
        assert data["status"] in ("success", "partial"), data
        assert len(data["data"]["results"]) > 0, f"{st} 应至少有一个情景结果"
        print(f"  {st}: {len(data['data']['results'])} 个情景")

    bad = _parse(portfolio_stress_test(FIXTURE_CODES, FIXTURE_WEIGHTS, scenario_type="unknown"))
    assert bad["status"] == "error"
    print("✅ 通过")


def test_rebalance_normal():
    print("=== 测试 portfolio_rebalance_suggestion 正常路径 ===")
    # 使用预计算分数文件中的真实代码
    scores = []
    scores_path = project_root / "recommender" / "portfolio_advisor" / "data" / "stock_dimension_scores.jsonl"
    with open(scores_path, encoding="utf-8") as f:
        for line in f:
            scores.append(json.loads(line)["code"])
    codes = scores[:4]
    weights = [0.25] * 4
    data = _parse(portfolio_rebalance_suggestion(codes, weights, max_actions=1, top_k=3))
    assert data["status"] in ("success", "partial"), data
    assert "scores_file" in data["data"]
    assert "plans" in data["data"]
    if data["data"]["plans"]:
        plan = data["data"]["plans"][0]
        for key in ("score_before", "score_after", "improvement", "actions"):
            assert key in plan, f"plan 缺少 {key}"
        print(f"方案数: {data['data']['plan_count']}, 首个方案提升: {plan['improvement']:.2f}")
    else:
        print("方案数: 0（当前组合已较优或无改进方案）")
    print("✅ 通过")


def test_rebalance_missing_scores_code():
    print("=== 测试调仓：当前组合含分数文件外的代码 ===")
    data = _parse(portfolio_rebalance_suggestion(["sz.999999"], [1.0]))
    assert data["status"] == "error", data
    assert "维度得分" in data["error"] or "调仓" in data["error"]
    print(f"错误信息: {data['error']}")
    print("✅ 通过")


def test_full_report():
    print("=== 测试 portfolio_full_report ===")
    data = _parse(portfolio_full_report(FIXTURE_CODES, FIXTURE_WEIGHTS))
    assert data["status"] in ("success", "partial"), data
    d = data["data"]
    assert "dimensions" in d and "risk" in d and "stress" in d and "report" in d
    assert len(d["stress"]["history"]) > 0
    assert d["report"]["health_score"] >= 0
    print(f"健康分: {d['report']['health_score']}, 历史场景: {len(d['stress']['history'])}, "
          f"宏观情景: {len(d['stress']['scenario'])}, 行业情景: {len(d['stress']['sector'])}")
    print("✅ 通过")


def run_all_tests():
    _patch_data()
    tests = [
        ("diagnosis_normal", test_diagnosis_normal),
        ("diagnosis_normalize", test_diagnosis_weight_auto_normalize),
        ("validate_errors", test_validate_errors),
        ("risk_alerts", test_risk_alerts),
        ("stress_history", test_stress_history),
        ("stress_scenario_sector", test_stress_scenario_and_sector),
        ("rebalance_normal", test_rebalance_normal),
        ("rebalance_missing_scores", test_rebalance_missing_scores_code),
        ("full_report", test_full_report),
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
    print(f"结果: {passed} 通过, {failed} 失败")
    return failed == 0


if __name__ == "__main__":
    run_all_tests()
