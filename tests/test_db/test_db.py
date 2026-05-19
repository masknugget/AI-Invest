import pandas as pd

from app.core.db.document import get_stock_daily_basic, get_stock_daily_technical, get_user_profile

a = get_stock_daily_basic("000001.SZ", "2025-01-01", "2025-12-31")
b = get_stock_daily_technical("000001.SZ", "2025-01-01", "2025-12-31")


print(pd.DataFrame(a))
print(pd.DataFrame(b))


a = get_stock_daily_basic("000001.SZ", "2025-06-16", "2025-06-16")


# ==================== get_user_profile 使用示例 ====================

print("\n=== get_user_profile 使用示例 ===")

# 示例1: 查询存在的用户画像
profile = get_user_profile("admin123")
if profile:
    print(f"✅ 找到用户画像")
    print(f"   user_id: {profile.get('user_id')}")
    print(f"   datetime: {profile.get('datetime')}")
    print(f"   generatedTags 数量: {len(profile.get('generatedTags', []))}")
    # 打印前3个标签
    for tag in profile.get('generatedTags', [])[:3]:
        print(f"   - [{tag.get('category')}] {tag.get('tag')} (置信度: {tag.get('confidence')})")
else:
    print("❌ 未找到用户画像，请先运行 user_profiles.py 生成")

# 示例2: 查询不存在的用户
profile_none = get_user_profile("non_existent_user")
if profile_none is None:
    print("\n✅ 不存在的用户返回 None，符合预期")

# 示例3: 获取完整画像数据用于推荐系统
print("\n=== 推荐系统集成示例 ===")
profile_for_rec = get_user_profile("admin123")
if profile_for_rec:
    # 提取兴趣主题
    topics = [
        tag["tag"] for tag in profile_for_rec.get("generatedTags", [])
        if tag.get("category") == "interest_topic"
    ]
    print(f"用户兴趣主题: {topics}")

    # 提取投资风格
    styles = [
        tag["tag"] for tag in profile_for_rec.get("generatedTags", [])
        if tag.get("category") == "trading_style"
    ]
    print(f"用户交易风格: {styles}")

    # 提取风险偏好
    risk_tags = [
        tag for tag in profile_for_rec.get("generatedTags", [])
        if tag.get("category") == "risk_signal"
    ]
    if risk_tags:
        print(f"风险信号: {risk_tags[0].get('tag')} (置信度: {risk_tags[0].get('confidence')})")