import pandas as pd
from pymongo import MongoClient, ASCENDING, UpdateOne
from decimal import Decimal
from datetime import datetime

file_path = r'G:\git_data\AI-Invest\data\技术面_合并.csv'


df = pd.read_csv(file_path, dtype=str)  # 先全部当字符串读，避免科学计数法


client = MongoClient("mongodb://localhost:27017")
db = client["stock_db"]
col = db["stock_daily_technical"]

# 仅当索引不存在时才创建
if "symbol_1_trade_date_1" not in {idx["name"] for idx in col.list_indexes()}:
    col.create_index([("symbol", ASCENDING), ("trade_date", ASCENDING)], unique=True)




# 2. 类型转换
from bson.decimal128 import Decimal128   # 新增

def to_decimal(s):
    return Decimal128(s) if pd.notna(s) else None


df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")
price_cols = ['open', 'open_hfq', 'open_qfq', 'high', 'high_hfq', 'high_qfq', 'low', 'low_hfq', 'low_qfq', 'close',
              'close_hfq', 'close_qfq', 'pre_close', 'change', 'pct_chg', 'vol', 'amount', 'turnover_rate',
              'turnover_rate_f', 'volume_ratio', 'pe', 'pe_ttm', 'pb', 'ps', 'ps_ttm', 'dv_ratio', 'dv_ttm', 'total_share',
              'float_share', 'dfma_dif_bfq', 'dfma_dif_hfq', 'dfma_dif_qfq', 'dfma_difma_bfq', 'dfma_difma_hfq',
              'dfma_difma_qfq', 'dmi_adx_bfq', 'dmi_adx_hfq', 'dmi_adx_qfq', 'dmi_adxr_bfq', 'dmi_adxr_hfq', 'dmi_adxr_qfq',
              'dmi_mdi_bfq', 'dmi_mdi_hfq', 'dmi_mdi_qfq', 'dmi_pdi_bfq', 'dmi_pdi_hfq', 'dmi_pdi_qfq', 'downdays', 'updays',
              'dpo_bfq', 'dpo_hfq', 'dpo_qfq', 'madpo_bfq', 'madpo_hfq', 'madpo_qfq', 'ema_bfq_10']
for c in price_cols:
    df[c] = df[c].apply(to_decimal)

# 3. 拼成 document 列表
docs = df.to_dict("records")

# 4. 批量 upsert（防重复跑）
requests = [
    UpdateOne(
        {"symbol": d["symbol"], "trade_date": d["trade_date"]},
        {"$set": d},
        upsert=True
    ) for d in docs
]
col.bulk_write(requests, ordered=False)


