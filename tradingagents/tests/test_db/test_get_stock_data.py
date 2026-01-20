from tradingagents.db.document import get_stock_data

symbol = '000001.SZ'
start_date = '2025-01-01'
end_date = '2025-10-10'


data = get_stock_data(symbol, start_date, end_date, "technical")
# data = get_stock_data(symbol, start_date, end_date, "basic")

import pandas as pd

df = pd.DataFrame(data)
base_cols = ["pb", "pe_ttm", "ps_ttm"]