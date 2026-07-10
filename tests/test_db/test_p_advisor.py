import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.db.p_advisor import save_industry_distribution, get_industry_distribution

sample_industry = {
    "Specialty Retailers": 0.7,
    "Natural Gas Utilities": 0.3,
}

user_id = "admin123"

print("=== save industry distribution ===")
save_industry_distribution(sample_industry, user_id=user_id)
print("save done")

print("\n=== get latest industry distribution ===")
latest = get_industry_distribution(user_id=user_id)
print("result:", latest)

assert latest is not None, "no industry distribution found"
assert latest.get("user_id") == user_id, f"user_id mismatch: {latest.get('user_id')}"
assert "date_time" in latest, "missing date_time field"
assert latest.get("distribution") == sample_industry, f"distribution mismatch: {latest.get('distribution')}"

print("\n[PASS] industry distribution save and get test passed")
