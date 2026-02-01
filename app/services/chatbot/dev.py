import requests
import json
import os

# 从环境变量获取API密钥，避免硬编码密钥
DASHSCOPE_API_KEY = "sk-12e56ecde21e49029ab895d80f357536"

# 构建请求数据
json_data = {
    "model": "qwen-plus",  # 指定使用的模型
    "temperature": 0.8,    # 控制生成内容的随机性，值越大越随机
    "frequency_penalty": 0.5,  # 控制重复内容的惩罚力度
    "max_tokens": 256,     # 最大生成token数
    "stream": False,       # 是否流式返回
    "messages": [
        {
            "role": "system",  # 系统角色，用于设定助手行为
            "content": "You are a helpful assistant."
        },
        {
            "role": "user",    # 用户角色，存放用户提问
            "content": "介绍下颐和园"
        }
    ]
}


# 发送POST请求调用API
resp = requests.post(
    url='https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions',
    headers={
        'Authorization': f'Bearer {DASHSCOPE_API_KEY}',  # 身份验证头
        'Content-Type': 'application/json',              # 数据格式声明
        'Accept': 'application/json'                     # 期望的响应格式
    },
    data=json.dumps(json_data, ensure_ascii=False)  # 将字典转换为JSON字符串
)

# 处理响应结果
if resp.status_code == 200:
    # 成功时提取并打印回复内容
    print(resp.json()['choices'][0]['message']['content'])
else:
    # 失败时打印状态码
    print(f"请求失败，状态码：{resp.status_code}")
