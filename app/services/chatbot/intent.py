from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.services.chatbot.prompts.p_intent import wrap_intent
from app.services.chatbot.tools import json_tools

# 初始化模型并绑定结构化输出
llm = ChatOpenAI(
    # 各地域的API Key不同。获取API Key：https://www.alibabacloud.com/help/zh/model-studio/get-api-key
    api_key="sk-12e56ecde21e49029ab895d80f357536",
    # 以下为新加坡地域base_url，若使用弗吉尼亚地域模型，需要将base_url换成https://dashscope-us.aliyuncs.com/compatible-mode/v1
    # 若使用北京地域的模型，需将base_url替换为：https://dashscope.aliyuncs.com/compatible-mode/v1
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    model="qwen-plus",
)

user_query = "你好啊"
prompt = wrap_intent(user_query,json_tools)
model_with_structure = llm.invoke(prompt)




def router_intent(user_query: str):
    pass
