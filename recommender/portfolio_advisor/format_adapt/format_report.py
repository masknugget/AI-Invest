from typing import Any, Dict, List, Optional

from pathlib import Path
import sys
import types
import json
from datetime import datetime
import pandas as pd

# 将项目根目录加入 sys.path，确保能导入 recommender 等模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

# mock openai，避免 recommender/__init__.py 链式导入失败
if "openai" not in sys.modules:
    _openai_mock = types.ModuleType("openai")
    setattr(_openai_mock, "OpenAI", type("OpenAI", (), {}))
    sys.modules["openai"] = _openai_mock

from recommender.portfolio_advisor.dimension.run import (
    PortfolioDimensions,
    compute_portfolio_dimensions,
)


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


def _rating_from_score(score: float) -> Dict[str, str]:
    """根据健康分生成评级信息。"""
    if score >= 80:
        return {"level": "excellent", "label": "优秀", "sub_label": "健康"}
    if score >= 60:
        return {"level": "good", "label": "良好", "sub_label": "亚健康"}
    if score >= 40:
        return {"level": "average", "label": "一般", "sub_label": "需关注"}
    return {"level": "poor", "label": "较差", "sub_label": "高风险"}


def format_report(
    result: PortfolioDimensions,
    comprehensive_str: str,
    score_history: Optional[List[Dict[str, Any]]] = None,
    update_time: Optional[str] = None,
    disclaimer: str = "以上评分由 AI 模型基于模拟持仓数据生成，仅供参考，不构成投资建议。市场有风险，投资需谨慎。",
) -> Dict[str, Any]:
    """
    将 PortfolioDimensions 与综合评语转换为
    mock/risk_diagnosis/report.json 对齐格式。

    Parameters
    ----------
    result : PortfolioDimensions
        compute_portfolio_dimensions 的输出。
    comprehensive_str : str
        综合评语，对应输出中的 comment。
    score_history : Optional[List[Dict[str, Any]]]
        历史得分曲线。为 None 时使用空列表。
    update_time : Optional[str]
        报告更新时间。为 None 时使用当前时间。
    disclaimer : str
        底部免责声明。

    Returns
    -------
    Dict[str, Any]
        与 report.json 结构一致的字典。
    """
    health_score = int(round(result.composite_score))

    if score_history is None:
        score_history = []

    if update_time is None:
        update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return {
        "health_score": health_score,
        "rating": _rating_from_score(health_score),
        "comment": comprehensive_str,
        "score_history": score_history,
        "update_time": update_time,
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

# 综合评语（实际场景中由 LLM 生成，此处使用示例字符串）
comprehensive_str = "你的持仓收益稳健，但行业集中度偏高，一旦相关行业调整，账户波动会显著加大。"

# 转换为 mock/risk_diagnosis/report.json 对齐格式并输出
formatted = format_report(
    result,
    comprehensive_str,
    score_history=[
        {"date": "2026-05-14", "score": 68},
        {"date": "2026-05-21", "score": 69},
        {"date": "2026-05-28", "score": 70},
        {"date": "2026-06-04", "score": 71},
        {"date": "2026-06-14", "score": int(round(result.composite_score))},
    ],
    update_time="2026-06-14 08:00:00",
)
print("\n【对齐后的 JSON 格式】")
print(json.dumps(formatted, ensure_ascii=False, indent=2))
