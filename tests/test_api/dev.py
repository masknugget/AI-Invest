from app.services.chatbot.chatbot_service import chat


user_query = "你是谁"
user_query = "000001的股价是多少"
for i in chat(user_query):
    print(i)