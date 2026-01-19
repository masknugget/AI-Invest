import pandas as pd
from pymongo import MongoClient, ASCENDING, UpdateOne
from datetime import datetime
import os

# Excel文件路径
file_path = r'G:\git_data\AI-Invest\data\事件数据.xlsx'  # 请根据实际文件路径修改

print("=" * 60)
print("开始导入事件数据到MongoDB...")
print(f"Excel文件路径: {file_path}")

# 检查文件是否存在
if not os.path.exists(file_path):
    print(f"❌ 错误: 文件 {file_path} 不存在!")
    print("请确保Excel文件已放置在正确位置")
    exit(1)

print("📖 正在读取Excel文件...")
# 读取Excel文件
df = pd.read_excel(file_path)
print(f"✅ 成功读取Excel文件，共 {len(df)} 条记录")

print("\n🔄 正在处理列名映射...")
print("原始列名:", list(df.columns))
# 列名映射
rename_map = {
    '代码': 'symbol',
    '简称': 'name',
    '事件类型': 'event_type',
    '具体事项': 'event_detail',
    '交易日': 'trade_date'
}
df.rename(columns=rename_map, inplace=True)
print("映射后的列名:", list(df.columns))
print("✅ 列名映射完成")

print("\n🔄 正在处理数据类型转换...")
# 数据类型转换
# 转换trade_date为datetime类型
df['trade_date'] = pd.to_datetime(df['trade_date'])
print("✅ 数据类型转换完成")

# 显示数据统计信息
print(f"\n📊 数据统计信息:")
print(f"数据时间范围: {df['trade_date'].min()} 到 {df['trade_date'].max()}")
print(f"事件类型分布:")
event_type_counts = df['event_type'].value_counts()
for event_type, count in event_type_counts.items():
    print(f"  {event_type}: {count} 条")

print("\n🔗 正在连接MongoDB...")
# 连接MongoDB
try:
    client = MongoClient("mongodb://localhost:27017")
    # 测试连接
    client.admin.command('ping')
    db = client['stock_db']
    coll = db['stock_events']
    print("✅ MongoDB连接成功")
    print(f"目标数据库: stock_db")
    print(f"目标集合: stock_events")
except Exception as e:
    print(f"❌ MongoDB连接失败: {e}")
    exit(1)

print("\n📝 正在生成唯一ID...")
# 生成唯一ID（symbol + trade_date + event_type）
df['_id'] = df['symbol'] + '_' + df['trade_date'].dt.strftime('%Y%m%d') + '_' + df['event_type']
print("✅ 唯一ID生成完成")

print(f"\n💾 正在写入MongoDB，共 {len(df)} 条记录...")
# 批量写入MongoDB（使用upsert避免重复）
requests = []
success_count = 0
batch_size = 1000

for i, record in enumerate(df.to_dict('records')):
    requests.append(
        UpdateOne({'_id': record['_id']}, {'$set': record}, upsert=True)
    )
    
    if len(requests) == batch_size:
        try:
            result = coll.bulk_write(requests, ordered=False)
            success_count += result.upserted_count + result.modified_count
            print(f"🔄 已处理 {i+1}/{len(df)} 条记录")
            requests.clear()
        except Exception as e:
            print(f"❌ 批量写入失败: {e}")
            requests.clear()

# 处理剩余的数据
if requests:
    try:
        result = coll.bulk_write(requests, ordered=False)
        success_count += result.upserted_count + result.modified_count
    except Exception as e:
        print(f"❌ 最后批量写入失败: {e}")

print(f"✅ 数据写入完成，成功处理 {success_count} 条记录")

print("\n🔑 正在创建索引...")
# 创建索引
try:
    coll.create_index([('symbol', ASCENDING), ('trade_date', ASCENDING)])
    print("✅ 创建复合索引: symbol + trade_date")
    
    coll.create_index([('event_type', ASCENDING)])
    print("✅ 创建索引: event_type")
    
    coll.create_index('trade_date')
    print("✅ 创建索引: trade_date")
    
    print("✅ 所有索引创建完成")
except Exception as e:
    print(f"⚠️ 索引创建警告: {e}")

print("\n" + "=" * 60)
print("🎉 事件数据导入完成！")
print(f"📈 总计导入: {success_count} 条记录")
print(f"📅 数据时间范围: {df['trade_date'].min().strftime('%Y-%m-%d')} 到 {df['trade_date'].max().strftime('%Y-%m-%d')}")
print(f"🏷️ 事件类型数量: {len(event_type_counts)} 种")
print("=" * 60)