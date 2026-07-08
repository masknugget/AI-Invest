from typing import Any, Dict, List, Optional

from pathlib import Path
import sys
import types
import json
import pandas as pd

# 将项目根目录加入 sys.path，确保能导入 recommender 等模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

# mock openai，避免 recommender/__init__.py 链式导入失败
if "openai" not in sys.modules:
    _openai_mock = types.ModuleType("openai")
    setattr(_openai_mock, "OpenAI", type("OpenAI", (), {}))
    sys.modules["openai"] = _openai_mock

from recommender.portfolio_advisor.analyst import generate_risks, parse_risks
from recommender.portfolio_advisor.dimension.run import compute_portfolio_dimensions


def _unwrap_df(item: Any) -> Any:
    """兼容 FileVisitor 可能返回 (key, df) 元组的情况。"""
    if isinstance(item, tuple):
        return item[1]
    return item


DATA_DIR = Path(r'F:\project_work\hf\AI-Invest\recommender\portfolio_advisor\data')


def _read_parquet(filename: str) -> pd.DataFrame:
    """读取单个 parquet 文件，文件不存在时抛出 FileNotFoundError。"""
    path = DATA_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"数据文件不存在: {path}")
    return pd.read_parquet(path)


def _infer_severity(summary: str, detail: str) -> str:
    """根据风险描述简单推断严重等级。"""
    text = (summary + detail).lower()
    high_keywords = ["清盘", "爆仓", "巨大", "致命", "极高", "严重", "过度集中", "崩塌"]
    low_keywords = ["轻微", "略有", "稍高", "偏弱"]
    if any(k in text for k in high_keywords):
        return "high"
    if any(k in text for k in low_keywords):
        return "low"
    return "medium"


def _severity_label(severity: str) -> str:
    """严重等级 -> 中文标签。"""
    return {"high": "高风险", "medium": "中风险", "low": "低风险"}.get(severity, "中风险")


def _severity_icon(severity: str) -> str:
    """严重等级 -> 图标标识。"""
    return {
        "high": "warning_high",
        "medium": "warning_medium",
        "low": "warning_low",
    }.get(severity, "warning_medium")


def format_risk_alerts(
    risks: List[Dict[str, str]],
    disclaimer: str = "以上风险提示由 AI 模型生成，仅供参考，不构成投资建议。",
) -> Dict[str, Any]:
    """
    将 parse_risks 返回的 List[Dict[str, str]] 转换为
    mock/risk_diagnosis/risk_alerts.json 对齐格式。

    源数据仅包含 summary/detail，因此输出中只保留能填充的字段：
    id / severity / severity_label / type_name / title / description / icon。
    源中不存在的 metrics / suggestion / type 等字段直接舍弃。

    Parameters
    ----------
    risks : List[Dict[str, str]]
        parse_risks 的输出，每个元素包含 summary 和 detail。
    disclaimer : str
        底部免责声明。

    Returns
    -------
    Dict[str, Any]
        与 risk_alerts.json 结构一致的字典。
    """
    alerts: List[Dict[str, Any]] = []

    for idx, risk in enumerate(risks):
        summary = risk.get("summary", "")
        detail = risk.get("detail", "")
        severity = _infer_severity(summary, detail)

        alert = {
            "id": f"risk_{idx + 1:03d}",
            "severity": severity,
            "severity_label": _severity_label(severity),
            "type_name": summary,
            "title": summary,
            "description": detail,
            "icon": _severity_icon(severity),
        }
        alerts.append(alert)

    return {
        "total_count": len(alerts),
        "alerts": alerts,
        "disclaimer": disclaimer,
    }


# 模块级变量：df_1 ~ df_5
df_1 = _read_parquet("df_1.parquet")
df_2 = _read_parquet("df_2.parquet")
df_3 = _read_parquet("df_3.parquet")

dfs = [df_1, df_2, df_3]
weights = [0.3, 0.3, 0.4]
codes = [str(df["code"].iloc[0]) for df in dfs]

# 5维度透视表
result = compute_portfolio_dimensions(dfs, weights)

print("=" * 70)
print("组合标的:", codes)
print("组合权重:", weights)
print("=" * 70)

print("【抗回撤能力】")
print(f"  最大回撤 MDD       : {result.drawdown_control.mdd:.4f}")
print(f"  控制得分 (0-100)   : {result.drawdown_control.score:.2f}")

print("\n【资产分散度】")
print(f"  ENB (weight-based) : {result.portfolio_diversification.enb_weight_based:.4f}")
print(f"  分散得分 (0-100)   : {result.portfolio_diversification.score:.2f}")

print("\n【持仓性价比】")
print(f"  夏普比率           : {result.position_efficiency.sharpe_ratio:.4f}")
print(f"  性价比得分 (0-100) : {result.position_efficiency.score:.2f}")

print("\n【收益稳定性】")
print(f"  年化波动率         : {result.return_stability.annualized_volatility:.4f}")
print(f"  稳定得分 (0-100)   : {result.return_stability.score:.2f}")

print("\n【风格均衡】")
print(f"  风格 HHI           : {result.style_balance.style_hhi:.4f}")
print(f"  均衡得分 (0-100)   : {result.style_balance.score:.2f}")

print("\n" + "=" * 70)
print(f"综合健康分 (0-100)    : {result.composite_score:.2f}")
print(f"几何加权综合分 (0-100) : {result.geometric_composite_score:.2f}")
print("=" * 70)

# 核心风险提示
sample_industry = {
    "消费/白酒": 0.40,
    "医药生物": 0.35,
    "新能源": 0.25,
}

raw_output = generate_risks(weights, sample_industry)
if raw_output is None:
    print("调用 LLM 失败，未获取到风险提示。")
else:
    risks = parse_risks(raw_output)
    print("\n【原始风险提示】")
    print(risks)

    # 转换为 mock/risk_diagnosis/risk_alerts.json 对齐格式并输出
    formatted = format_risk_alerts(risks)
    print("\n【对齐后的 JSON 格式】")
    print(json.dumps(formatted, ensure_ascii=False, indent=2))
