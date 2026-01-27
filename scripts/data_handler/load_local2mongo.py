import pandas as pd
from pymongo import MongoClient, ASCENDING, UpdateOne
from decimal import Decimal
from datetime import datetime
import os

print("=" * 60)
print("开始导入技术面数据到MongoDB...")

file_path = r'G:\vibe\cleandata\data\技术面_合并.csv'

# 检查文件是否存在
if not os.path.exists(file_path):
    print(f"❌ 错误: 文件 {file_path} 不存在!")
    print("请确保CSV文件已放置在正确位置")
    exit(1)

print(f"📖 正在读取CSV文件: {file_path}")
df = pd.read_csv(file_path, dtype=str)  # 先全部当字符串读，避免科学计数法
print(f"✅ 成功读取CSV文件，共 {len(df)} 条记录")
print(f"📊 数据列名: {list(df.columns)}")


print("\n🔗 正在连接MongoDB...")
try:
    client = MongoClient("mongodb://localhost:27017")
    # 测试连接
    client.admin.command('ping')
    db = client["stock_db"]
    col = db["stock_daily_technical"]
    print("✅ MongoDB连接成功")
    print(f"目标数据库: stock_db")
    print(f"目标集合: stock_daily_technical")
except Exception as e:
    print(f"❌ MongoDB连接失败: {e}")
    exit(1)

# 检查并创建索引
print("\n🔑 正在检查索引...")
if "symbol_1_trade_date_1" not in {idx["name"] for idx in col.list_indexes()}:
    print("📝 创建复合索引: symbol + trade_date")
    col.create_index([("symbol", ASCENDING), ("trade_date", ASCENDING)], unique=True)
    print("✅ 索引创建完成")
else:
    print("✅ 索引已存在，无需创建")




print("\n🔄 正在处理数据类型转换...")
# 2. 类型转换
from bson.decimal128 import Decimal128   # 新增

def to_decimal(s):
    return Decimal128(s) if pd.notna(s) else None

print("📅 正在转换交易日期...")
df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")
print(f"✅ 交易日期转换完成，时间范围: {df['trade_date'].min()} 到 {df['trade_date'].max()}")

print("💰 正在转换价格相关字段...")
price_cols = ['open', 'open_hfq', 'open_qfq', 'high', 'high_hfq', 'high_qfq', 'low', 'low_hfq', 'low_qfq', 'close',
              'close_hfq', 'close_qfq', 'pre_close', 'change', 'pct_chg', 'vol', 'amount', 'turnover_rate',
              'turnover_rate_f', 'volume_ratio', 'pe', 'pe_ttm', 'pb', 'ps', 'ps_ttm', 'dv_ratio', 'dv_ttm', 'total_share',
              'float_share', 'dfma_dif_bfq', 'dfma_dif_hfq', 'dfma_dif_qfq', 'dfma_difma_bfq', 'dfma_difma_hfq',
              'dfma_difma_qfq', 'dmi_adx_bfq', 'dmi_adx_hfq', 'dmi_adx_qfq', 'dmi_adxr_bfq', 'dmi_adxr_hfq', 'dmi_adxr_qfq',
              'dmi_mdi_bfq', 'dmi_mdi_hfq', 'dmi_mdi_qfq', 'dmi_pdi_bfq', 'dmi_pdi_hfq', 'dmi_pdi_qfq', 'downdays', 'updays',
              'dpo_bfq', 'dpo_hfq', 'dpo_qfq', 'madpo_bfq', 'madpo_hfq', 'madpo_qfq', 'ema_bfq_10']

print(f"📝 需要转换的字段数量: {len(price_cols)}")
for i, c in enumerate(price_cols):
    df[c] = df[c].apply(to_decimal)
    if i % 10 == 0 and i > 0:
        print(f"🔄 已转换 {i}/{len(price_cols)} 个字段")

print("✅ 所有价格字段转换完成")

print("\n📋 正在准备批量写入数据...")
# 3. 拼成 document 列表
docs = df.to_dict("records")
print(f"✅ 文档列表准备完成，共 {len(docs)} 条记录")

# 4. 批量 upsert（防重复跑）
print(f"\n💾 正在写入MongoDB，共 {len(docs)} 条记录...")
batch_size = 1000
requests = []
success_count = 0

for i, d in enumerate(docs):
    requests.append(
        UpdateOne(
            {"symbol": d["symbol"], "trade_date": d["trade_date"]},
            {"$set": d},
            upsert=True
        )
    )
    
    if len(requests) == batch_size:
        try:
            result = col.bulk_write(requests, ordered=False)
            success_count += result.upserted_count + result.modified_count
            print(f"🔄 已处理 {i+1}/{len(docs)} 条记录")
            requests.clear()
        except Exception as e:
            print(f"❌ 批量写入失败: {e}")
            requests.clear()

# 处理剩余的数据
if requests:
    try:
        result = col.bulk_write(requests, ordered=False)
        success_count += result.upserted_count + result.modified_count
    except Exception as e:
        print(f"❌ 最后批量写入失败: {e}")

print(f"✅ 数据写入完成，成功处理 {success_count} 条记录")

# 显示数据统计信息
print(f"\n📊 数据统计信息:")
print(f"数据时间范围: {df['trade_date'].min()} 到 {df['trade_date'].max()}")
print(f"股票代码数量: {df['symbol'].nunique()} 只")
print(f"数据完整性: {success_count}/{len(docs)} 条记录成功处理")

print("\n" + "=" * 60)
print("🎉 技术面数据导入完成！")
print(f"📈 总计导入: {success_count} 条记录")
print(f"📅 数据时间范围: {df['trade_date'].min().strftime('%Y-%m-%d')} 到 {df['trade_date'].max().strftime('%Y-%m-%d')}")
print(f"🏷️ 股票数量: {df['symbol'].nunique()} 只")
print("=" * 60)


