from typing import Any, Dict, List, Mapping, Optional

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


def format_dimensions(
    result: PortfolioDimensions,
    benchmark: Optional[List[Dict[str, Any]]] = None,
    disclaimer: str = "以上维度评分由 AI 模型生成，仅供参考，不构成投资建议。",
) -> Dict[str, Any]:
    """
    将 compute_portfolio_dimensions 的 PortfolioDimensions 结果转换为
    mock/risk_diagnosis/dimensions.json 对齐格式。

    Parameters
    ----------
    result : PortfolioDimensions
        compute_portfolio_dimensions 的输出。
    benchmark : Optional[List[Dict[str, Any]]]
        各维度市场平均得分。为 None 时使用与 mock 一致的默认值。
    disclaimer : str
        底部免责声明。

    Returns
    -------
    Dict[str, Any]
        与 dimensions.json 结构一致的字典。
    """
    if benchmark is None:
        benchmark = [
            {"key": "return_stability", "avg_score": 68},
            {"key": "style_balance", "avg_score": 72},
            {"key": "cost_performance", "avg_score": 66},
            {"key": "drawback_resistance", "avg_score": 64},
            {"key": "industry_diversification", "avg_score": 70},
        ]

    dimension_items: List[Dict[str, Any]] = [
        {
            "key": "return_stability",
            "name": "收益稳定性",
            "score": int(round(result.return_stability.score)),
            "weight": 0.20,
            "description": "近一年收益波动较小"
            if result.return_stability.score >= 70
            else "收益波动相对明显",
        },
        {
            "key": "style_balance",
            "name": "风格均衡",
            "score": int(round(result.style_balance.score)),
            "weight": 0.20,
            "description": "成长与价值风格配置较为均衡"
            if result.style_balance.score >= 70
            else "成长与价值风格配置尚不均衡",
        },
        {
            "key": "cost_performance",
            "name": "持仓性价比",
            "score": int(round(result.position_efficiency.score)),
            "weight": 0.20,
            "description": "整体估值处于合理区间"
            if result.position_efficiency.score >= 60
            else "整体估值性价比偏低",
        },
        {
            "key": "drawback_resistance",
            "name": "抗回撤能力",
            "score": int(round(result.drawdown_control.score)),
            "weight": 0.20,
            "description": "最大回撤控制尚可"
            if result.drawdown_control.score >= 60
            else "最大回撤控制有待加强",
        },
        {
            "key": "industry_diversification",
            "name": "行业分散度",
            "score": int(round(result.portfolio_diversification.score)),
            "weight": 0.20,
            "description": "行业配置相对分散"
            if result.portfolio_diversification.score >= 60
            else "行业集中度偏高，存在单一行业依赖",
        },
    ]

    return {
        "dimensions": dimension_items,
        "benchmark": benchmark,
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

# 转换为 mock/risk_diagnosis/dimensions.json 对齐格式并输出
formatted = format_dimensions(result)
print("\n【对齐后的 JSON 格式】")
print(json.dumps(formatted, ensure_ascii=False, indent=2))
