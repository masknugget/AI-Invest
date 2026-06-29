"""
生成单股五维得分 JSONL（含股票代码与日期窗口）。

输出格式示例：
    {
        "code": "000001.SZ",
        "start_date": "2023-01-01",
        "end_date": "2024-01-01",
        "drawdown_control": 11.27,
        "portfolio_diversification": 100.0,
        "position_efficiency": 6.02,
        "return_stability": 51.68,
        "style_balance": 0.0
    }
"""

import os
from typing import Dict, List

from tqdm import tqdm

from infra_structure.data_engine.visitor.file_visitor import FileVisitor
from research.portfolio_advisor.dimension.run_one import compute_stock_dimensions
from research.portfolio_advisor.utils import save_jsonl

file_visitor = FileVisitor("basic", "stock", "market", "d1", "time_series").data_set()

cnt = 0
data_result: List[Dict] = []
for item in tqdm(file_visitor.iter(), total=len(file_visitor), desc="处理股票数据"):
    df = item[1] if isinstance(item, tuple) else item
    if df is None:
        continue

    cnt += 1
    if cnt > 100:
        break

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

output_path = os.path.join(r"D:\q_project\quantq\research\portfolio_advisor", "data", "stock_dimension_scores.jsonl")
save_jsonl(data_result, output_path)
print(f"已保存 {len(data_result)} 条结果到: {output_path}")
