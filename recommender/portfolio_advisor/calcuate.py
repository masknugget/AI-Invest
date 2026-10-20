"""
从 tradingagents 的 stock_daily_quotes 集合读取 A 股日线行情，
逐只股票计算五维诊断指标（复用 run_one.compute_stock_dimensions），
并将结果保存到 p_advisor_cal_dimensions 集合。

数据说明
--------
- stock_daily_quotes 字段: symbol / code / full_symbol / market /
  trade_date(字符串 'YYYY-MM-DD') / open / high / low / close /
  pre_close / volume / amount / change / pct_chg。
- compute_stock_dimensions 需要包含 'date'、'close'、'pctChg' 列的 DataFrame。
"""

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from pymongo import MongoClient

# 保证可从工程根目录导入 recommender 包（直接运行本脚本时）
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from recommender.portfolio_advisor.dimension.run_one import compute_stock_dimensions

# ==================== MongoDB 连接与集合配置 ====================
MONGO_URI = "mongodb://localhost:27017"
SOURCE_DB = "tradingagents"          # stock_daily_quotes 行情所在库
BASIC_DB = "tradingagents"           # stock_basic_info 基础信息所在库（如无名称可指向实际有数据的库）
TARGET_DB = "tradingagentscn"        # p_advisor_cal_dimensions 输出库（与 app.core.db._init_db 及 get_all_cal_dimension 读取库一致）
QUOTES_COLLECTION = "stock_daily_quotes"
BASIC_COLLECTION = "stock_basic_info"
TARGET_COLLECTION = "p_advisor_cal_dimensions"

# 计算所用的行情日期区间（trade_date 为 ISO 字符串，可直接按字典序比较）
START_DATE = "2020-01-01"
END_DATE = "2026-05-01"

client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=8000)
source_db = client[SOURCE_DB]
basic_db = client[BASIC_DB]
target_db = client[TARGET_DB]
quotes_coll = source_db[QUOTES_COLLECTION]
basic_coll = basic_db[BASIC_COLLECTION]
target_coll = target_db[TARGET_COLLECTION]


def load_daily_quotes(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """按 symbol + 日期区间读取日线行情，返回按日期升序、清洗后的 DataFrame。"""
    cursor = quotes_coll.find(
        {"symbol": symbol, "trade_date": {"$gte": start_date, "$lte": end_date}},
        {"_id": 0},
    ).sort("trade_date", 1)
    records = list(cursor)
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["trade_date"])
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    # 去除无效/异常价格并按日期升序
    df = df[df["close"] > 0].sort_values("date").reset_index(drop=True)
    return df


def build_pct_chg(df: pd.DataFrame) -> pd.DataFrame:
    """构造日涨跌幅列 pctChg（百分比制）：优先使用集合内 pct_chg，缺失时由 close 推算。"""
    if "pct_chg" in df.columns and pd.to_numeric(df["pct_chg"], errors="coerce").notna().any():
        df["pctChg"] = pd.to_numeric(df["pct_chg"], errors="coerce")
    else:
        df["pctChg"] = 100 * (df["close"] / df["close"].shift(1) - 1)
    return df


def get_basic_info(symbol: str) -> dict:
    """从 stock_basic_info 查询股票名称/行业等基础信息，缺失时返回空字典。"""
    doc = basic_coll.find_one({"symbol": symbol}, {"_id": 0})
    if not doc:
        doc = basic_coll.find_one({"code": symbol}, {"_id": 0})
    return doc or {}


def main() -> None:
    unique_symbols = quotes_coll.distinct("symbol")
    print(f"待处理股票数量: {len(unique_symbols)}")

    saved = 0
    for symbol in unique_symbols:
        try:
            df_data = load_daily_quotes(symbol, START_DATE, END_DATE)
            if df_data.empty or len(df_data) < 2:
                print(f"跳过 {symbol}: 有效行情不足")
                continue

            df_data = build_pct_chg(df_data)
            result = compute_stock_dimensions(df_data)
            print(symbol)
            info = get_basic_info(symbol)
            full_symbol = info.get("full_symbol", "")
            if not full_symbol and "full_symbol" in df_data.columns:
                full_symbol = str(df_data["full_symbol"].iloc[0])
            market = str(df_data["market"].iloc[0]) if "market" in df_data.columns else ""

            result_dict = {
                "code": symbol,
                "name": info.get("name", ""),
                "full_symbol": full_symbol,
                "industry": info.get("industry", ""),
                "market": market,
                "start_date": str(df_data["date"].iloc[0].date()),
                "end_date": str(df_data["date"].iloc[-1].date()),
                **result.to_score_dict(),
                "composite_score": result.composite_score,
                "geometric_composite_score": result.geometric_composite_score,
            }

            log_entry = {"timestamp": datetime.now(), **result_dict}
            target_coll.insert_one(log_entry)
            saved += 1
            print(f"已保存 {symbol} {result_dict['name']}")
        except Exception as e:
            print(f"{symbol} 计算失败: {e}")
            continue

    print(f"处理完成，成功保存 {saved} 条记录到 {TARGET_DB}.{TARGET_COLLECTION}")


if __name__ == "__main__":
    main()
