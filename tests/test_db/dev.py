
from datetime import datetime, timezone, timedelta

from app.core.db.document import get_user_profile, log_rec_history, get_rec_history
from scripts.data_handler.news.prompt_userprofiles import USER_PROFILE_TAGS
from tradingagents.searcher import VectorStore


def get_tag_name(name_str):
    """
    获取tag
    Args:
        name_str:

    Returns:

    """
    if name_str in USER_PROFILE_TAGS:
        return USER_PROFILE_TAGS[name_str]
    return name_str



user_id = "admin123"
profile = get_user_profile(user_id)
tags = profile["generatedTags"]

tags_names = [i.get('tag') for i in tags]
tags_zn = [get_tag_name(i) for i in tags_names]



# 推荐历史
history = get_rec_history(user_id)


# 召回
vector_store = VectorStore('insight_news')


result = []
for tag in tags_zn:
    vector = vector_store.search(tag, top_k=5)
    result.extend(vector)


dt_dict = {}
for item in result:
    if item.id in history:
        continue
    dt_dict[item.id] = item

result = list(dt_dict.values())

# 评分排序
result_sorted = sorted(result, key=lambda x: x.score, reverse=True)

result_sorted = result_sorted[:3]


# 记录推荐历史
rec_ids = [i.id for i in result_sorted]
data_rec_log = {
    'user_id': user_id,
    'rec_content_ids': rec_ids,
    'create_datetime': datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
}


log_rec_history(data_rec_log)


out_data = []
for item in result_sorted:
    data = {
        "content": item.content,
        "uuid": item.metadata.get('uuid'),
        "data_ner": item.metadata.get('data_ner'),
        "data_label": item.metadata.get('data_label'),
        "data_event": item.metadata.get('data_event'),
        "data_report": item.metadata.get('data_report'),
    }
    out_data.append(data)

