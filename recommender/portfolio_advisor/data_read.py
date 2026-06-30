"""
Portfolio advisor data reader.

读取 recommender/portfolio_advisor/data/ 下的 df_1.parquet ~ df_5.parquet，
并将其分别赋值给模块级变量 df_1 ~ df_5。
"""

from pathlib import Path
from typing import Dict

import pandas as pd

# 数据文件目录（本文件所在目录下的 data 文件夹）
DATA_DIR = Path(r'F:\project_work\hf\AI-Invest\recommender\portfolio_advisor\data')


def _read_parquet(filename: str) -> pd.DataFrame:
    """读取单个 parquet 文件，文件不存在时抛出 FileNotFoundError。"""
    path = DATA_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"数据文件不存在: {path}")
    return pd.read_parquet(path)


# 模块级变量：df_1 ~ df_5
df_1 = _read_parquet("df_1.parquet")
df_2 = _read_parquet("df_2.parquet")
df_3 = _read_parquet("df_3.parquet")
df_4 = _read_parquet("df_4.parquet")
df_5 = _read_parquet("df_5.parquet")


def load_all() -> Dict[str, pd.DataFrame]:
    """
    返回包含 df_1 ~ df_5 的字典，便于批量处理。

    Returns:
        Dict[str, pd.DataFrame]: {"df_1": df_1, ..., "df_5": df_5}
    """
    return {
        "df_1": df_1,
        "df_2": df_2,
        "df_3": df_3,
        "df_4": df_4,
        "df_5": df_5,
    }


if __name__ == "__main__":
    data = load_all()
    for name, df in data.items():
        print(f"{name}: shape={df.shape}, columns={list(df.columns)}")
