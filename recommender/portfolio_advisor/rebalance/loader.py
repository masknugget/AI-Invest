"""
候选股票池加载器。

支持从 stock_dimension_scores.jsonl 加载候选股票及其预计算五维得分。
优化调仓仅依赖该 JSONL 中的 dimension_scores，不再加载行情 DataFrame。
"""

import warnings
from typing import Any, List, Optional, Protocol

import pandas as pd

from recommender.portfolio_advisor.rebalance.types import CandidatePool, StockCandidate
from recommender.portfolio_advisor.utils import load_jsonl


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


def load_stock_scores_from_jsonl(path: str) -> dict[str, dict]:
    """
    从 stock_dimension_scores.jsonl 加载所有股票的维度得分。

    Parameters
    ----------
    path : str
        JSONL 文件路径。

    Returns
    -------
    dict[str, dict]
        以股票 code 为键、五维得分字典为值的映射。
    """
    records = load_jsonl(path)
    return {
        str(record["code"]): _extract_dimension_scores(record)
        for record in records
        if "code" in record
    }


def load_code_name_from_jsonl(path: str) -> dict[str, str]:
    """
    从 stock_dimension_scores.jsonl 加载所有股票的code和name。

    Parameters
    ----------
    path : str
        JSONL 文件路径。

    Returns
    -------
    dict[str, dict]
        以股票 code 为键、五维得分字典为值的映射。
    """
    records = load_jsonl(path)
    return {
        str(record["code"]): str(record["name"])
        for record in records
        if "code" in record
    }


def get_current_stock_scores(current_codes: List[str], scores_path: str) -> List[dict]:
    """
    从 stock_dimension_scores.jsonl 加载当前组合各股票的维度得分。

    Parameters
    ----------
    current_codes : List[str]
        当前组合标的代码。
    scores_path : str
        stock_dimension_scores.jsonl 文件路径。

    Returns
    -------
    List[dict]
        与 current_codes 顺序一致的五维得分列表。

    Raises
    ------
    ValueError
        当前组合中存在股票在 scores_path 中找不到维度得分。
    """
    all_scores = load_stock_scores_from_jsonl(scores_path)
    missing = [code for code in current_codes if code not in all_scores]
    if missing:
        raise ValueError(
            f"当前组合中以下股票缺少维度得分，请检查 {scores_path}: {missing}"
        )
    return [all_scores[code] for code in current_codes]


def _load_df_for_code(code: str, file_visitor: Optional[Any] = None) -> Optional[pd.DataFrame]:
    """根据股票代码从 FileVisitor 拉取完整行情 DataFrame。"""
    if file_visitor is None:
        return None
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
    limit: Optional[int] = None,
    fetch_full_df: bool = True,
    file_visitor: Optional[Any] = None,
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
        是否尝试通过 file_visitor 拉取完整行情 DataFrame。拉取失败时跳过该候选。
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

        df = None
        if fetch_full_df:
            df = _load_df_for_code(code, file_visitor)
            if df is None:
                warnings.warn(f"无法为股票 {code} 拉取完整行情，跳过该候选。")
                continue

        candidates.append(
            StockCandidate(
                code=code,
                dimension_scores=dimension_scores,
                df=df,
            )
        )

    return candidates


def load_candidate_pool_from_jsonl_as_pool(
    path: str,
    require_code: bool = True,
    limit: Optional[int] = None,
    fetch_full_df: bool = True,
    file_visitor: Optional[Any] = None,
) -> CandidatePool:
    """以 CandidatePool 对象形式返回候选池。"""
    candidates = load_candidate_pool_from_jsonl(
        path,
        require_code=require_code,
        limit=limit,
        fetch_full_df=fetch_full_df,
        file_visitor=file_visitor,
    )
    return CandidatePool(candidates=candidates)
