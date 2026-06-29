"""
候选股票池加载器。

支持从 stock_dimension_scores.jsonl 加载候选股票，并根据 code 字段
通过 FileVisitor 拉取完整行情 DataFrame。
"""

import warnings
from typing import Any, List, Optional, Protocol

import pandas as pd

from research.portfolio_advisor.rebalance.types import CandidatePool, StockCandidate
from research.portfolio_advisor.utils import load_jsonl


DIMENSION_NAMES = {
    "drawdown_control",
    "portfolio_diversification",
    "position_efficiency",
    "return_stability",
    "style_balance",
}


class _DataSet(Protocol):
    """FileVisitor.data_set() 返回对象的协议，避免依赖具体类型。"""

    def get(self, code: str) -> pd.DataFrame: ...


def _extract_dimension_scores(record: dict) -> dict:
    """从 JSONL 记录中提取五维得分。"""
    return {dim: float(record[dim]) for dim in DIMENSION_NAMES if dim in record}


def _load_df_for_code(code: str, file_visitor: Optional[Any] = None) -> Optional[pd.DataFrame]:
    """根据股票代码从 FileVisitor 拉取完整行情 DataFrame。"""
    if file_visitor is None:
        # 延迟导入，避免模块加载时触发 FileVisitor 初始化
        from infra_structure.data_engine.visitor.file_visitor import FileVisitor

        file_visitor = FileVisitor("basic", "stock", "market", "d1", "time_series").data_set()
    try:
        df = file_visitor.get(code)
        if df is None or df.empty:
            return None
        return df
    except Exception:  # noqa: BLE001
        return None


def load_candidate_pool_from_jsonl(
    path: str,
    require_code: bool = True,
    fetch_full_df: bool = True,
    file_visitor: Optional[Any] = None,
    limit: Optional[int] = None,
) -> List[StockCandidate]:
    """
    从 stock_dimension_scores.jsonl 加载候选池。

    Parameters
    ----------
    path : str
        JSONL 文件路径。
    require_code : bool, default True
        是否要求每条记录必须包含 code 字段。若为 True 且缺失，抛出 ValueError。
    fetch_full_df : bool, default True
        是否尝试通过 FileVisitor 拉取完整行情 DataFrame。
    file_visitor : Optional[Any]
        外部传入的 FileVisitor.data_set() 实例，避免重复构造。
    limit : Optional[int], default None
        最多加载前 N 条有效记录。None 表示不限制。用于示例脚本避免全量加载导致长时间无响应。

    Returns
    -------
    List[StockCandidate]
        候选股票列表。
    """
    records = load_jsonl(path)
    if limit is not None and limit > 0:
        records = records[:limit]
    candidates: List[StockCandidate] = []

    for idx, record in enumerate(records):
        if "code" not in record:
            if require_code:
                raise ValueError(
                    f"第 {idx + 1} 行缺少 'code' 字段，请重新运行 one.py 生成包含 code 的数据。"
                )
            # 不强制要求时跳过无 code 的记录
            continue

        code = str(record["code"])
        dimension_scores = _extract_dimension_scores(record)

        df: Optional[pd.DataFrame] = None
        if fetch_full_df:
            df = _load_df_for_code(code, file_visitor)

        if df is None:
            # 无法拉取完整行情时给出警告并跳过
            warnings.warn(f"无法为股票 {code} 拉取完整行情，跳过该候选。", stacklevel=2)
            continue

        candidates.append(
            StockCandidate(
                code=code,
                df=df,
                dimension_scores=dimension_scores,
            )
        )

    return candidates


def load_candidate_pool_from_jsonl_as_pool(
    path: str,
    require_code: bool = True,
    fetch_full_df: bool = True,
    file_visitor: Optional[Any] = None,
    limit: Optional[int] = None,
) -> CandidatePool:
    """以 CandidatePool 对象形式返回候选池。"""
    candidates = load_candidate_pool_from_jsonl(
        path,
        require_code=require_code,
        fetch_full_df=fetch_full_df,
        file_visitor=file_visitor,
        limit=limit,
    )
    return CandidatePool(candidates=candidates)

