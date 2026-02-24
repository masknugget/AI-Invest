from langchain_core.output_parsers import JsonOutputParser

from app.core.db.document import get_chat_history
from app.services.chatbot.chatbot_service import chat


JsonOutputParser
for user_query in [
    "你是谁",
    "平安银行的股价是多少",
    "平安银行进行基本面分析"
]:
    for i in chat(user_query, conversation_id='123'):
        print(i)
