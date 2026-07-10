"""
生成单股五维得分 JSONL（含股票代码与日期窗口）。

用法：
    python recommender/portfolio_advisor/one.py

说明：
    本脚本读取 recommender/portfolio_advisor/data/ 下的 df_1.parquet ~ df_5.parquet，
    计算每只股票的五维得分，并保存到同一目录下的 stock_dimension_scores.jsonl。

输出格式示例：
    {
        "code": "sh.600000",
        "start_date": "2020-10-15",
        "end_date": "2026-05-08",
        "drawdown_control": 11.27,
        "portfolio_diversification": 100.0,
        "position_efficiency": 6.02,
        "return_stability": 51.68,
        "style_balance": 50.0
    }
"""

import os
import sys
import types
from typing import Dict, List

# 将项目根目录加入路径，使本脚本可直接运行
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# mock openai，避免触发 recommender/__init__.py 中的大量依赖链
if "openai" not in sys.modules:
    _openai_mock = types.ModuleType("openai")
    setattr(_openai_mock, "OpenAI", type("OpenAI", (), {}))
    sys.modules["openai"] = _openai_mock

from recommender.portfolio_advisor.data_read import load_all
from recommender.portfolio_advisor.dimension.run_one import compute_stock_dimensions
from recommender.portfolio_advisor.utils import save_jsonl


def main():
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    output_path = os.path.join(data_dir, "stock_dimension_scores.jsonl")

    data_result: List[Dict] = []
    for name, df in load_all().items():
        if df is None or df.empty:
            continue

        code = str(df["code"].iloc[0])
        start_date = str(df["date"].iloc[0])
        end_date = str(df["date"].iloc[-1])

        result = compute_stock_dimensions(df)

        result_dict: Dict = {
            "code": code,
            "start_date": start_date,
            "end_date": end_date,
            **result.to_score_dict(),
        }
        data_result.append(result_dict)
        print(f"已处理 {name}: {code}")

    save_jsonl(data_result, output_path)
    print(f"已保存 {len(data_result)} 条结果到: {output_path}")


if __name__ == "__main__":
    main()
