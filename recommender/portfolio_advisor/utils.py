import json
from pathlib import Path
from typing import Any, Iterable, List, Union

import pandas as pd
import numpy as np


# ============================================================================
# JSONL 工具函数
# ============================================================================


def save_jsonl(
    data: Iterable[Any],
    path: Union[str, Path],
    ensure_ascii: bool = False,
    **json_dumps_kwargs: Any,
) -> None:
    """
    将可迭代对象按 JSONL 格式写入文件。

    参数
    ----------
    data : Iterable[Any]
        待保存的数据序列，每个元素会被 json.dumps 序列化。
    path : Union[str, Path]
        目标文件路径。
    ensure_ascii : bool, default False
        是否强制 ASCII 编码；False 时保留中文等非 ASCII 字符可读。
    **json_dumps_kwargs
        透传给 json.dumps 的额外参数，例如 default、sort_keys 等。
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        for item in data:
            line = json.dumps(item, ensure_ascii=ensure_ascii, **json_dumps_kwargs)
            f.write(line + "\n")


def load_jsonl(
    path: Union[str, Path],
    **json_loads_kwargs: Any,
) -> List[Any]:
    """
    从 JSONL 文件读取数据。

    参数
    ----------
    path : Union[str, Path]
        JSONL 文件路径。
    **json_loads_kwargs
        透传给 json.loads 的额外参数。

    返回
    -------
    List[Any]
        文件中每一行解析后的对象列表。
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"JSONL 文件不存在: {path}")

    results = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            results.append(json.loads(line, **json_loads_kwargs))

    return results


# ============================================================================
# 组合构建
# ============================================================================


def build_portfolio(
        dfs: list[pd.DataFrame],
        weights: list[float],
        align: str = 'inner'  # 'inner': 日期交集; 'outer': 日期并集
) -> pd.DataFrame:
    """
    将 List[pd.DataFrame] + List[float] 合并为投资组合 DataFrame
    自动按 date 对齐，并处理不同列的加权逻辑
    """
    assert len(dfs) == len(weights), "dfs 和 weights 长度必须一致"

    # 权重归一化
    weights = np.array(weights, dtype=float)
    weights = weights / weights.sum()

    # 列分类策略
    price_cols = ['open', 'high', 'low', 'close', 'preclose']
    sum_cols = ['volume']
    min_cols = ['tradestatus']
    avg_cols = ['turn', 'peTTM', 'pbMRQ', 'psTTM', 'pcfNcfTTM']

    # 1. 日期对齐
    all_dates = sorted(set().union(*[set(df['date']) for df in dfs]))

    if align == 'inner':
        trade_dates = set(dfs[0]['date'])
        for df in dfs[1:]:
            trade_dates &= set(df['date'])
        trade_dates = sorted(trade_dates)
    else:
        trade_dates = all_dates

    # 2. 逐列合成
    result = pd.DataFrame({'date': trade_dates})

    for col in price_cols + sum_cols + min_cols + avg_cols + ['pctChg']:
        if not all(col in df.columns for df in dfs):
            continue

        # 收集各资产对齐后的值
        mat = np.zeros((len(trade_dates), len(dfs)))
        valid = np.zeros((len(trade_dates), len(dfs)), dtype=bool)

        for i, df in enumerate(dfs):
            s = df.set_index('date')[col].reindex(trade_dates)
            mat[:, i] = s.values
            valid[:, i] = s.notna().values

        if col in price_cols + avg_cols:
            # 加权平均（缺失资产权重自动重新分配给其他资产）
            w = np.where(valid, weights, 0)
            w_sum = w.sum(axis=1, keepdims=True)
            w_sum = np.where(w_sum == 0, 1, w_sum)
            result[col] = (mat * w / w_sum).sum(axis=1)

        elif col in sum_cols:
            # 求和（缺失视为0）
            result[col] = np.where(valid, mat, 0).sum(axis=1)

        elif col in min_cols:
            # 最小值（缺失视为0，即停牌）
            result[col] = np.where(valid, mat, 0).min(axis=1).astype(int)

    # 3. 从合成价格重新计算收益率（最准确）
    if 'close' in result.columns and 'preclose' in result.columns:
        result['pctChg'] = (result['close'] - result['preclose']) / result['preclose']

    result['code'] = 'PORTFOLIO'

    # 调整列顺序
    ordered = ['date', 'code'] + price_cols + ['preclose'] + sum_cols + min_cols + ['pctChg'] + avg_cols
    ordered = [c for c in ordered if c in result.columns]
    return result[ordered]

# ========== 使用示例 ==========
# portfolio_df = build_portfolio([df1, df2, df3], [0.4, 0.3, 0.3], align='inner')