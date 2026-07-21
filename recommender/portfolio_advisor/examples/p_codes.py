import sys
from pathlib import Path

# 将项目根目录加入 sys.path，确保可以导入 app 模块
PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.db.p_advisor import save_portfolio_codes, get_portfolio_codes


weights = [0.3, 0.3, 0.4]
# codes = [str(df["code"].iloc[0]) for df in dfs]
codes = ["sh.600008", "sh.600009", "sh.600010"]
names = ["首创环保", "上海机场", "包钢股份"]

industry_data = {
    "sh.600008": "Natural Gas Utilities",
    "sh.600009": "Specialty Retailers",
    "sh.600010": "Specialty Retailers",
}


data = [
    {
        "code": "sh.600008",
        "name": "首创环保",
        "industry": "Natural Gas Utilities",
        "weight": 0.3
    },
    {
        "code": "sh.600009",
        "name": "上海机场",
        "industry": "Specialty Retailers",
        "weight": 0.3
    },
    {
        "code": "sh.600010",
        "name": "包钢股份",
        "industry": "Specialty Retailers",
        "weight": 0.4
    }
]


user_id = "admin123"


if __name__ == "__main__":
    # 保存 portfolio 代码数据到 MongoDB
    save_portfolio_codes(data, user_id=user_id)
    print(f"已保存 portfolio 代码到 MongoDB，user_id={user_id}")

    # 按 user_id 查询最新的 portfolio 代码数据
    latest = get_portfolio_codes(user_id=user_id)
    if latest:
        print("\n查询到最新记录:")
        print(f"  date_time: {latest.get('date_time')}")
        print(f"  data: {latest.get('data')}")
    else:
        print("\n未查询到 portfolio 代码记录")
