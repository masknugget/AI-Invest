import pandas as pd
from pymongo import MongoClient, ASCENDING, UpdateOne
from datetime import datetime

file_path = r'G:\vibe\cleandata\data\基本面_合并.xlsx'  # 或者 csv
df = pd.read_excel(file_path)  # csv 就用 read_csv


# 4. 写 Mongo
client = MongoClient("mongodb://localhost:27017")
db = client['stock_db']
coll = db['stock_daily_basic']



# 1. 列名英文化（可选，方便后面代码）
rename_map = {
    '日期': 'trade_date',
    '代码': 'symbol',
    '名称': 'name',
    '行业': 'industry',
    '城市': 'city',
    '上市日期': 'ipo_date',
    '总股本(亿)': 'total_shares',
    '流通股本(亿)': 'float_shares',
    '总资产(亿)': 'total_assets',
    '流动资产(亿)': 'current_assets',
    '固定资产(亿)': 'fixed_assets',
    '每股净资产': 'bps',
    '每股收益': 'eps',
    '市盈率(动)': 'pe_ttm',
    '市净率': 'pb',
    '未分配利润': 'retained_profit',
    '每股未分配利润': 'retained_profit_per_share',
    '公积金': 'reserve',
    '每股公积金': 'reserve_per_share',
    '毛利率%': 'gross_margin',
    '净利润率%': 'net_margin',
    '收入同比%': 'revenue_yoy',
    '利润同比%': 'profit_yoy',
    '股东人数': 'holder_num'
}
df.rename(columns=rename_map, inplace=True)

# 2. 类型转换
date_cols = ['trade_date']
for c in date_cols:
    df[c] = pd.to_datetime(df[c].astype('str'))

df['ipo_date'] = df['ipo_date'].astype('str')

numeric_cols = ['total_shares', 'float_shares', 'total_assets', 'current_assets',
                'fixed_assets', 'bps', 'eps', 'pe_ttm', 'pb',
                'retained_profit', 'retained_profit_per_share',
                'reserve', 'reserve_per_share',
                'gross_margin', 'net_margin', 'revenue_yoy', 'profit_yoy', 'holder_num']
for c in numeric_cols:
    df[c] = pd.to_numeric(df[c], errors='coerce')

# 3. 生成 _id 字段，保证 symbol+trade_date 唯一
df['_id'] = df['symbol'] + '_' + df['trade_date'].dt.strftime('%Y%m%d')


requests = []
for record in df.to_dict('records'):
    requests.append(
        UpdateOne({'_id': record['_id']}, {'$set': record}, upsert=True)
    )
    if len(requests) == 1000:  # 每 1000 条刷一次
        coll.bulk_write(requests, ordered=False)
        requests.clear()
if requests:
    coll.bulk_write(requests, ordered=False)

# 5. 建索引
coll.create_index([('symbol', ASCENDING), ('trade_date', ASCENDING)])
coll.create_index('trade_date')  # 如果经常按日期范围查，再单建一个
print('done')
