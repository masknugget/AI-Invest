"""
候选股票池加载器。

从 MongoDB 的 p_advisor_cal_dimensions 集合（app.core.db.get_all_cal_dimension）
加载候选股票及其预计算五维得分，不再读取本地 JSONL 文件。
优化调仓仅依赖其中的 dimension_scores，不加载行情 DataFrame。
"""

import warnings
from typing import Any, List, Optional, Protocol

import pandas as pd

from app.core.db import get_all_cal_dimension
from recommender.portfolio_advisor.rebalance.types import CandidatePool, StockCandidate


DIMENSION_NAMES = {
    "drawdown_control",
    "portfolio_diversification",
    "position_efficiency",
    "return_stability",
    "style_balance",
}

# one.py 持久化的可选原始指标（旧版得分文件无这些字段，存在才提取）
METRIC_NAMES = (
    "mdd",
    "sharpe_ratio",
    "annualized_volatility",
    "enb_weight_based",
    "style_hhi",
)


class _DataSet(Protocol):
    """FileVisitor.data_set() 返回对象的协议，避免依赖具体类型。"""

    def get(self, code: str) -> pd.DataFrame: ...


def _extract_dimension_scores(record: dict) -> dict:
    """从维度记录中提取五维得分；原始指标（如 mdd）存在时一并带出。"""
    scores = {dim: float(record[dim]) for dim in DIMENSION_NAMES if dim in record}
    for metric in METRIC_NAMES:
        if metric in record:
            scores[metric] = float(record[metric])
    return scores


def _load_records() -> List[dict]:
    """
    从 MongoDB p_advisor_cal_dimensions 读取全部标的维度记录（已按 code 去重）。

    get_all_cal_dimension 在集合为空或查询异常时可能返回非 list 结构，
    此处统一兜底为空列表，避免调用方处理多种返回类型。
    """
    data = get_all_cal_dimension()
    if not isinstance(data, list):
        return []
    return [record for record in data if isinstance(record, dict)]


def load_stock_scores_from_jsonl(path: Optional[str] = None) -> dict[str, dict]:
    """
    从 MongoDB p_advisor_cal_dimensions 加载所有股票的维度得分。

    Parameters
    ----------
    path : Optional[str]
        已废弃，保留仅为向后兼容；数据来源改为 MongoDB，不再读取本地文件。

    Returns
    -------
    dict[str, dict]
        以股票 code 为键、五维得分字典为值的映射。
    """
    records = _load_records()
    return {
        str(record["code"]): _extract_dimension_scores(record)
        for record in records
        if "code" in record
    }


def load_code_name_from_jsonl(path: Optional[str] = None) -> dict[str, str]:
    """
    从 MongoDB p_advisor_cal_dimensions 加载所有股票的 code 和 name。

    Parameters
    ----------
    path : Optional[str]
        已废弃，保留仅为向后兼容；数据来源改为 MongoDB，不再读取本地文件。

    Returns
    -------
    dict[str, str]
        以股票 code 为键、name 为值的映射。缺少 name 字段的记录自动跳过。
    """
    records = _load_records()
    return {
        str(record["code"]): str(record["name"])
        for record in records
        if "code" in record and "name" in record
    }


def get_current_stock_scores(current_codes: List[str], scores_path: Optional[str] = None) -> List[dict]:
    """
    从 MongoDB p_advisor_cal_dimensions 加载当前组合各股票的维度得分。

    Parameters
    ----------
    current_codes : List[str]
        当前组合标的代码。
    scores_path : Optional[str]
        已废弃，保留仅为向后兼容；数据来源改为 MongoDB，不再读取本地文件。

    Returns
    -------
    List[dict]
        与 current_codes 顺序一致的五维得分列表。

    Raises
    ------
    ValueError
        当前组合中存在股票在 p_advisor_cal_dimensions 中找不到维度得分。
    """
    all_scores = load_stock_scores_from_jsonl()
    missing = [code for code in current_codes if code not in all_scores]
    if missing:
        raise ValueError(
            f"当前组合中以下股票缺少维度得分，请检查 p_advisor_cal_dimensions: {missing}"
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
    path: Optional[str] = None,
    require_code: bool = True,
    limit: Optional[int] = None,
    fetch_full_df: bool = True,
    file_visitor: Optional[Any] = None,
) -> List[StockCandidate]:
    """
    从 MongoDB p_advisor_cal_dimensions 加载候选池。

    Parameters
    ----------
    path : Optional[str]
        已废弃，保留仅为向后兼容；数据来源改为 MongoDB，不再读取本地文件。
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
    records = _load_records()
    if limit is not None and limit > 0:
        records = records[:limit]
    candidates: List[StockCandidate] = []

    for idx, record in enumerate(records):
        if "code" not in record:
            if require_code:
                raise ValueError(
                    f"第 {idx + 1} 条记录缺少 'code' 字段，请检查 p_advisor_cal_dimensions 数据。"
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
    path: Optional[str] = None,
    require_code: bool = True,
    limit: Optional[int] = None,
    fetch_full_df: bool = True,
    file_visitor: Optional[Any] = None,
) -> CandidatePool:
    """以 CandidatePool 对象形式返回候选池（数据来源：MongoDB p_advisor_cal_dimensions）。"""
    candidates = load_candidate_pool_from_jsonl(
        path,
        require_code=require_code,
        limit=limit,
        fetch_full_df=fetch_full_df,
        file_visitor=file_visitor,
    )
    return CandidatePool(candidates=candidates)
