"""
Portfolio Advisor MCP 工具公共层。

职责：
- 统一响应封装（status / tool / data / warnings / error）
- 参数校验（股票代码、权重）
- 行情 DataFrame 获取（多源冗余：MongoDB -> akshare/yfinance）
- 行业查询冗余封装
- 预计算分数文件检查
- 引擎模块安全导入（data_read 存在硬编码路径与模块级 IO，做注入兜底）

所有工具均为同步纯计算函数，docstring 即 MCP tool 描述。
"""
from __future__ import annotations

import json
import sys
import types
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[5]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 预计算五维得分文件（调仓引擎依赖）
SCORES_PATH = (
    PROJECT_ROOT / "recommender" / "portfolio_advisor" / "data" / "stock_dimension_scores.jsonl"
)

# 分数文件过期阈值（天）
SCORES_MAX_AGE_DAYS = 7

# 行情回看年限
QUOTE_LOOKBACK_YEARS = 3

MAX_PORTFOLIO_SIZE = 20


# ============================================================================
# 引擎模块安全导入
# ============================================================================

def _ensure_engine_importable() -> None:
    """
    recommender.portfolio_advisor.data_read 存在硬编码 F:\\ 路径与模块级 parquet IO，
    导入失败会导致 dimension.run / rebalance.scoring 等整条链不可用。
    这里先探测导入，失败则注入仅提供 load_all 占位实现的 stub 模块，
    使计算引擎（不依赖 load_all 的部分）可以正常导入。
    """
    try:
        import recommender.portfolio_advisor.data_read  # noqa: F401
        return
    except Exception:
        stub = types.ModuleType("recommender.portfolio_advisor.data_read")

        def _unavailable(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("data_read 本地 fixture 不可用（部署环境无 parquet 数据）")

        stub.load_all = _unavailable  # type: ignore[attr-defined]
        sys.modules["recommender.portfolio_advisor.data_read"] = stub


_ensure_engine_importable()


def get_dimension_run():
    """惰性导入五维评分引擎入口。"""
    from recommender.portfolio_advisor.dimension import run as dimension_run

    return dimension_run


def get_format_advisor():
    from recommender.portfolio_advisor.format_adapt import format_advisor

    return format_advisor


# ============================================================================
# 统一响应封装
# ============================================================================

def make_response(
    tool: str,
    data: Any = None,
    status: str = "success",
    warnings: Optional[List[str]] = None,
    error: Optional[str] = None,
) -> str:
    """构造统一 JSON 字符串响应，与现有 MCP 工具（返回 str）保持一致。"""
    payload = {
        "status": status,
        "tool": tool,
        "data": data,
        "warnings": warnings or [],
        "error": error,
    }
    return json.dumps(_to_jsonable(payload), ensure_ascii=False)


def error_response(tool: str, message: str) -> str:
    return make_response(tool, status="error", error=message)


def _to_jsonable(obj: Any) -> Any:
    """将 numpy / pandas / dataclass / datetime 等转换为 JSON 可序列化类型。"""
    if obj is None or isinstance(obj, (bool, int, str)):
        return obj
    if isinstance(obj, float):
        return obj if obj == obj and abs(obj) != float("inf") else str(obj)  # NaN/inf
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_to_jsonable(v) for v in obj]
    # numpy 标量
    if hasattr(obj, "item"):
        try:
            return _to_jsonable(obj.item())
        except Exception:
            pass
    if isinstance(obj, (datetime,)):
        return obj.strftime("%Y-%m-%d")
    if isinstance(obj, pd.DataFrame):
        return obj.to_dict(orient="records")
    if hasattr(obj, "__dataclass_fields__"):
        from dataclasses import asdict

        return _to_jsonable(asdict(obj))
    return str(obj)


# ============================================================================
# 参数校验
# ============================================================================

def validate_portfolio(codes: List[str], weights: List[float]) -> Tuple[List[str], List[float]]:
    """
    校验并归一化组合参数。

    - codes: 非空、去空白、无重复、数量不超过 MAX_PORTFOLIO_SIZE
    - weights: 长度与 codes 一致、全部非负、至少一个为正；总和允许 != 1，内部归一化

    返回 (codes, normalized_weights)；非法时抛 ValueError（中文信息）。
    """
    if not codes:
        raise ValueError("股票代码列表不能为空")
    if not weights:
        raise ValueError("权重列表不能为空")
    if len(codes) != len(weights):
        raise ValueError(
            f"股票代码数量({len(codes)})与权重数量({len(weights)})不一致"
        )
    if len(codes) > MAX_PORTFOLIO_SIZE:
        raise ValueError(f"组合标的数量过多（{len(codes)}），上限为 {MAX_PORTFOLIO_SIZE}")

    clean_codes = [str(c).strip() for c in codes]
    if any(not c for c in clean_codes):
        raise ValueError("存在空白股票代码")
    dup = [c for c in set(clean_codes) if clean_codes.count(c) > 1]
    if dup:
        raise ValueError(f"存在重复股票代码: {dup}")

    try:
        clean_weights = [float(w) for w in weights]
    except (TypeError, ValueError):
        raise ValueError("权重必须为数值")
    if any(w < 0 for w in clean_weights):
        raise ValueError("权重不能为负数")
    total = sum(clean_weights)
    if total <= 0:
        raise ValueError("权重总和必须为正数")

    return clean_codes, [w / total for w in clean_weights]


def build_portfolio_arg(codes: List[str], weights: List[float]) -> List[Dict[str, Any]]:
    """构造压力测试引擎所需的 portfolio 参数。"""
    return [{"code": c, "weight": w} for c, w in zip(codes, weights)]


# ============================================================================
# 股票代码格式候选（多格式冗余探测）
# ============================================================================

def _symbol_candidates(code: str) -> List[str]:
    """根据 baostock 风格代码（sh.600000 / sz.000001 / hk.00700）生成各数据源可能使用的格式。"""
    c = code.strip()
    candidates: List[str] = [c]
    if "." in c:
        market, num = c.split(".", 1)
        market = market.lower()
        if market in ("sh", "sz", "bj"):
            candidates += [num, f"{market}{num}", f"{num}.SH", f"{num}.SZ", f"{num}.BJ"]
        elif market == "hk":
            candidates += [num, f"{num}.HK", f"{num.zfill(5)}.HK"]
        else:  # us 等
            candidates += [num.upper(), f"{num.upper()}.US"]
    else:
        candidates += [c.upper()]
    # 保序去重
    seen: set = set()
    result = []
    for x in candidates:
        if x and x not in seen:
            seen.add(x)
            result.append(x)
    return result


def detect_code_market(code: str) -> str:
    """粗略识别市场：cn / hk / us / unknown。"""
    try:
        from tradingagents.db.document import detect_market

        for sym in _symbol_candidates(code):
            m = detect_market(sym)
            if m != "unknown":
                return m
        return "unknown"
    except Exception:
        pass
    c = code.strip().lower()
    if c.startswith(("sh.", "sz.", "bj.")):
        return "cn"
    if c.startswith("hk."):
        return "hk"
    return "unknown"


# ============================================================================
# 行情数据获取（多源冗余：MongoDB -> akshare(CN) -> yfinance(HK/US)）
# ============================================================================

_QUOTE_FIELD_ALIASES = {
    "date": ["trade_date", "date", "日期", "Date"],
    "close": ["close", "收盘", "Close", "adj_close", "Adj Close"],
    "pctChg": ["pctChg", "pct_chg", "changepercent", "涨跌幅", "PctChg"],
    "code": ["symbol", "code", "股票代码"],
}


def _pick_column(df: pd.DataFrame, aliases: List[str]) -> Optional[str]:
    for name in aliases:
        if name in df.columns:
            return name
    return None


def _records_to_df(records: List[Dict[str, Any]], code: str) -> Optional[pd.DataFrame]:
    """将 MongoDB 记录统一转换为 引擎所需的 date/code/close/pctChg DataFrame。"""
    if not records:
        return None
    df = pd.DataFrame(records)
    date_col = _pick_column(df, _QUOTE_FIELD_ALIASES["date"])
    close_col = _pick_column(df, _QUOTE_FIELD_ALIASES["close"])
    if not date_col or not close_col:
        return None
    out = pd.DataFrame(
        {
            "date": pd.to_datetime(df[date_col]).dt.strftime("%Y-%m-%d"),
            "code": code,
            "close": pd.to_numeric(df[close_col], errors="coerce"),
        }
    )
    pct_col = _pick_column(df, _QUOTE_FIELD_ALIASES["pctChg"])
    if pct_col:
        # akshare 风格的 pctChg 为百分数数值，统一除以 100
        raw = pd.to_numeric(df[pct_col], errors="coerce")
        out["pctChg"] = raw / 100.0 if raw.abs().median() > 1.5 else raw
    else:
        out["pctChg"] = out["close"].pct_change()
    out = out.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)
    if len(out) < 2:
        return None
    return out


def _fetch_quote_from_db(code: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    try:
        from tradingagents.db.document import get_stock_data
    except Exception:
        return None
    for sym in _symbol_candidates(code):
        try:
            records = get_stock_data(sym, start_date, end_date, "technical")
        except Exception:
            continue
        df = _records_to_df(records, code)
        if df is not None:
            return df
    return None


def _fetch_quote_from_akshare(code: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    if detect_code_market(code) != "cn":
        return None
    num = code.split(".", 1)[1] if "." in code else code
    try:
        import akshare as ak

        df = ak.stock_zh_a_hist(
            symbol=num, period="daily", start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""), adjust="qfq",
        )
    except Exception:
        return None
    return _records_to_df(df.to_dict(orient="records"), code)


def _fetch_quote_from_yfinance(code: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    if detect_code_market(code) == "cn":
        return None
    candidates = [s for s in _symbol_candidates(code) if s.endswith(".HK") or "." not in s]
    try:
        import yfinance as yf
    except Exception:
        return None
    for sym in candidates:
        try:
            df = yf.download(sym, start=start_date, end=end_date, progress=False)
        except Exception:
            continue
        if df is None or df.empty:
            continue
        df = df.reset_index()
        records = df.to_dict(orient="records")
        out = _records_to_df(records, code)
        if out is not None:
            return out
    return None


def fetch_quote_df(code: str, lookback_years: int = QUOTE_LOOKBACK_YEARS) -> pd.DataFrame:
    """
    获取单只标的历史行情 DataFrame（date/code/close/pctChg 列）。

    多源冗余：MongoDB(tradingagents.db.document) -> akshare(A股) -> yfinance(港美股)。
    全部失败时抛 ValueError（中文信息）。
    """
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=365 * lookback_years)).strftime("%Y-%m-%d")

    df = _fetch_quote_from_db(code, start_date, end_date)
    if df is not None:
        return df
    df = _fetch_quote_from_akshare(code, start_date, end_date)
    if df is not None:
        return df
    df = _fetch_quote_from_yfinance(code, start_date, end_date)
    if df is not None:
        return df
    raise ValueError(
        f"无法获取 {code} 的历史行情（已尝试 MongoDB / akshare / yfinance），"
        "请确认数据已入库或网络可用"
    )


def fetch_quotes(codes: List[str]) -> Dict[str, pd.DataFrame]:
    """批量获取行情，任一失败即抛错（附带已成功/失败明细）。"""
    dfs: Dict[str, pd.DataFrame] = {}
    failed: List[str] = []
    for code in codes:
        try:
            dfs[code] = fetch_quote_df(code)
        except Exception:
            failed.append(code)
    if failed:
        ok = [c for c in codes if c not in failed]
        raise ValueError(f"以下标的行情获取失败: {failed}（成功: {ok}）")
    return dfs


# ============================================================================
# 行业查询（MongoDB 冗余，失败归入未知）
# ============================================================================

def industry_lookup(code: str) -> Optional[str]:
    """查询股票所属行业；失败返回 None（由调用方归入未知行业）。"""
    try:
        from tradingagents.db.document import get_stock_info
    except Exception:
        return None
    for sym in _symbol_candidates(code):
        try:
            info = get_stock_info(sym)
        except Exception:
            continue
        if info and info.get("industry"):
            return info["industry"]
    return None


def build_industry_distribution(codes: List[str], weights: List[float]) -> Dict[str, float]:
    """按权重聚合一级行业分布，查询不到归入 未知行业。"""
    dist: Dict[str, float] = {}
    for code, w in zip(codes, weights):
        industry = industry_lookup(code) or "未知行业"
        dist[industry] = dist.get(industry, 0.0) + w
    return dist


# ============================================================================
# 预计算分数文件检查
# ============================================================================

def check_scores_file(max_age_days: int = SCORES_MAX_AGE_DAYS) -> Tuple[Path, List[str]]:
    """
    检查 stock_dimension_scores.jsonl 存在性与时效。

    返回 (path, warnings)；文件缺失抛 ValueError。
    """
    if not SCORES_PATH.exists():
        raise ValueError(
            f"预计算分数文件不存在: {SCORES_PATH}，"
            "请先运行候选池离线打分（compute_stock_dimensions）生成 stock_dimension_scores.jsonl"
        )
    warnings: List[str] = []
    mtime = datetime.fromtimestamp(SCORES_PATH.stat().st_mtime)
    age_days = (datetime.now() - mtime).days
    if age_days > max_age_days:
        warnings.append(
            f"预计算分数文件已 {age_days} 天未更新（阈值 {max_age_days} 天），调仓建议时效性可能不足"
        )
    return SCORES_PATH, warnings


def scores_file_meta() -> Dict[str, Any]:
    """返回分数文件元信息（路径/更新时间/大小）。"""
    try:
        path, _ = check_scores_file()
        stat = path.stat()
        return {
            "path": str(path),
            "updated_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            "size_bytes": stat.st_size,
        }
    except ValueError as e:
        return {"path": str(SCORES_PATH), "error": str(e)}
