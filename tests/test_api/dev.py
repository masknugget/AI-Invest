from collections import defaultdict

from app.core.db.document import get_chat_history
from app.services.chatbot.chatbot_service import chat


# user_query = "你是谁"
# user_query = "平安银行的股价是多少"
# user_query = "平安银行进行基本面分析"
# for i in chat(user_query, conversation_id='1234'):
#     print(i)



chat_history = get_chat_history("")

# 按 conversation_id 分组
grouped = defaultdict(list)
for item in chat_history:
    key = item['conversation_id']
    grouped[key].append(item)



result = []
# 查看结果
for conv_id, items in grouped.items():
    title = items[0].get("title", "")
    create_datetime = items[0].get("create_datetime", "")
    messages = []
    for item in items:
        messages.extend(item.get("messages", []))


    data_item = {
        "conversation_id": conv_id,
        "create_datetime": create_datetime,
        "title": title,
        "messages": messages,
    }
    result.append(data_item)