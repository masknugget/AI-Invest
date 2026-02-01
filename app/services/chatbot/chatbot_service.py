from app.services.chatbot.llm_direct_call import post, post_stream


def chat(user_query):
    json_data = {
        "model": "qwen-plus",  # 指定使用的模型
        "temperature": 0.8,  # 控制生成内容的随机性，值越大越随机
        "frequency_penalty": 0.5,  # 控制重复内容的惩罚力度
        "max_tokens": 256,  # 最大生成token数
        "stream": True,  # 是否流式返回
        "messages": [
            {
                "role": "system",  # 系统角色，用于设定助手行为
                "content": "You are a helpful assistant."
            },
            {
                "role": "user",  # 用户角色，存放用户提问
                "content": user_query
            }
        ]
    }

    yield from post_stream(json_data)