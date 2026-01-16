import pandas as pd

from app.core.db.document import get_stock_daily_basic, get_stock_daily_technical

a = get_stock_daily_basic("000001.SZ", "2025-01-01", "2025-12-31")
b = get_stock_daily_technical("000001.SZ", "2025-01-01", "2025-12-31")


print(pd.DataFrame(a))
print(pd.DataFrame(b))


a = get_stock_daily_basic("000001.SZ", "2025-06-16", "2025-06-16")