"""
Portfolio Advisor MCP 工具 —— 数据获取层。

职责：
- 股票代码格式候选与市场探测（多格式冗余：sh.600000 / 600000 / 600000.SH ...）
- 行情 DataFrame 获取（多源冗余：MongoDB -> akshare(A股) -> yfinance(港美股)）
- 行业查询与行业分布聚合

所有函数返回引擎所需的标准结构（date/code/close/pctChg DataFrame），
不处理响应封装与参数校验（见 _common.py）。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from bson.decimal128 import Decimal128
import pandas as pd

# 行情回看年限
QUOTE_LOOKBACK_YEARS = 3

# ---------------------------------------------------------------------------
# 【本地开发环境】本地 MongoDB 行情源
# 线上环境行情位于 stock_db.stock_daily_technical；本地通常没有该库，
# 改从本地 tradingagents.stock_daily_quotes 读取。上线部署时，只需注释掉
# _fetch_quote_from_db 中对 _fetch_quote_from_local_mongo 的调用即可。
# ---------------------------------------------------------------------------
LOCAL_MONGO_URI = "mongodb://localhost:27017"
LOCAL_QUOTES_DB = "tradingagents"
LOCAL_QUOTES_COLL = "stock_daily_quotes"


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
    "volume": ["vol", "成交量", "Volume", "VOLUME", "volume"],
    "pctChg": ["pctChg", "pct_chg", "changepercent", "涨跌幅", "PctChg"],
    "code": ["symbol", "code", "股票代码"],
}


def _pick_column(df: pd.DataFrame, aliases: List[str]) -> Optional[str]:
    for name in aliases:
        if name in df.columns:
            return name
    return None


def _to_numeric_series(values: pd.Series) -> pd.Series:
    """先解包 MongoDB Decimal128，再转换数值；无效值保留为 NaN。"""
    values = values.map(lambda value: value.to_decimal() if isinstance(value, Decimal128) else value)
    return pd.to_numeric(values, errors="coerce")


def _records_to_df(records: List[Dict[str, Any]], code: str) -> Optional[pd.DataFrame]:
    """将 MongoDB / akshare / yfinance 记录统一转换为引擎所需的 date/code/close/pctChg DataFrame。"""
    if not records:
        return None
    df = pd.DataFrame(records)
    date_col = _pick_column(df, _QUOTE_FIELD_ALIASES["date"])
    close_col = _pick_column(df, _QUOTE_FIELD_ALIASES["close"])
    volume_col = _pick_column(df, _QUOTE_FIELD_ALIASES["volume"])
    if not date_col or not close_col:
        return None
    out = pd.DataFrame(
        {
            "date": pd.to_datetime(df[date_col]).dt.strftime("%Y-%m-%d"),
            "code": code,
            "close": _to_numeric_series(df[close_col],),
            "volume": _to_numeric_series(df[volume_col]) if volume_col else float("nan"),
        }
    )
    pct_col = _pick_column(df, _QUOTE_FIELD_ALIASES["pctChg"])
    if pct_col:
        # akshare 风格的 pctChg 为百分数数值，统一除以 100
        raw = _to_numeric_series(df[pct_col])
        out["pctChg"] = raw / 100.0 if raw.abs().median() > 1.5 else raw
    else:
        out["pctChg"] = out["close"].pct_change()
    out = out.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)
    if len(out) < 2:
        return None
    return out

def _fetch_quote_from_daily_performance(
    code: str, start_date: str, end_date: str,
) -> Optional[pd.DataFrame]:
    """解析股票代码并获取港股/A股日线；共享接口目前最多返回最近 60 条。"""
    try:
        from app.core.db.document import get_daily_performance, search_symbol
    except Exception:
        return None

    queried = set()
    for candidate in _symbol_candidates(code):
        try:
            info = search_symbol(candidate)
            if not info or not info.get("symbol"):
                continue
            symbol = str(info["symbol"]).strip()
            market = str(info.get("market") or "HK").strip().upper()
            if not symbol or market not in {"HK", "CN"}:
                continue
            key = (symbol, market)
            if key in queried:
                continue
            queried.add(key)
            _, data_out = get_daily_performance(symbol, start_date, end_date, market=market)
            records = pd.DataFrame(data_out).to_dict("records")
            df = _records_to_df(records, code)
            if df is not None:
                return df
        except Exception:
            continue
    return None


def _fetch_quote_from_local_mongo(code: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    """
    【本地开发环境专用】从本地 MongoDB 的 tradingagents.stock_daily_quotes 读取日线行情。

    线上环境行情位于 stock_db.stock_daily_technical（见 _fetch_quote_from_db 其余分支），
    本地通常没有该库，因此这里直接读本地已入库的 stock_daily_quotes 作为优先数据源。
    上线部署时，只需注释掉 _fetch_quote_from_db 中对本函数的调用即可。

    数据格式：symbol/code 为纯 6 位（如 '000001'），full_symbol 为 '000001.SZ'，
    trade_date 为字符串 'YYYY-MM-DD'（按字符串区间过滤），
    pct_chg 为百分数（如 2.86 表示 2.86%），此处统一转为小数再交给 _records_to_df。
    """
    try:
        from pymongo import MongoClient
    except Exception:
        return None

    candidates = _symbol_candidates(code)
    client = MongoClient(LOCAL_MONGO_URI)
    try:
        coll = client[LOCAL_QUOTES_DB][LOCAL_QUOTES_COLL]
        query = {
            "$or": [
                {"symbol": {"$in": candidates}},
                {"full_symbol": {"$in": candidates}},
                {"code": {"$in": candidates}},
            ],
            "trade_date": {"$gte": start_date, "$lte": end_date},
        }
        records = list(coll.find(query, {"_id": 0}))
        if not records:
            return None
        # stock_daily_quotes.pct_chg 为百分数，统一转小数，避免 _records_to_df 的量纲启发式误判
        for rec in records:
            pct = rec.get("pct_chg")
            if pct is not None:
                try:
                    rec["pct_chg"] = float(pct) / 100.0
                except (TypeError, ValueError):
                    pass
        return _records_to_df(records, code)
    except Exception:
        return None
    finally:
        client.close()


def _fetch_quote_from_db(code: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    # ===== 本地开发环境：优先读本地 MongoDB(tradingagents.stock_daily_quotes) =====
    # 上线部署时，注释掉下面 3 行即可（其余分支走线上 stock_db 数据源）。
    local_df = _fetch_quote_from_local_mongo(code, start_date, end_date)
    if local_df is not None:
        return local_df
    # ===== 本地开发环境结束 =====

    df = _fetch_quote_from_daily_performance(code, start_date, end_date)
    if df is not None:
        return df
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
