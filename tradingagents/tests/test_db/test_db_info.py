from tradingagents.db.document import get_stock_news
from tradingagents.utils.indicators import add_all_indicators

symbol = '000730.SZ'
start_date = '2025-01-01'
end_date = '2025-10-10'


symbol = 'code.'+symbol.split('.')[0]
data = get_stock_news(symbol, start_date, end_date)
# data = get_stock_data(symbol, start_date, end_date, "basic")

import pandas as pd

df = pd.DataFrame(data)


def convert_data(item):
    return float(item.to_decimal())


df['close'] = df['close'].map(convert_data)
df = add_all_indicators(df)

col = ['trade_date','pb', 'pct_chg', 'pe_ttm', 'ps_ttm',]
col_num = ['pb', 'pct_chg', 'pe_ttm', 'ps_ttm',]
df[col_num] = df[col_num].round(2)
df = df.tail(60)
df_data = df.to_dict('list')

content = ""

data = ["""
基本面指标数据：pb, pe_ttm, ps_ttm
pct_chg为涨幅
"""]
for key in col:
    value = df_data[key]
    if key == 'trade_date':
        value = [i.strftime("%Y%m%d") for i in value]
    else:
        value = [str(i) for i in value]
    value_str = " ".join(value)
    line_content = key + ": " + value_str
    data.append(line_content)

content = "\n".join(data)


from pprint import pprint
pprint(content)
