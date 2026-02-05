from typing import Dict

import requests
import json
import os

# 从环境变量获取API密钥，避免硬编码密钥
DASHSCOPE_API_KEY = "sk-12e56ecde21e49029ab895d80f357536"


def post(json_data: Dict):
    resp = requests.post(
        url='https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions',
        headers={
            'Authorization': f'Bearer {DASHSCOPE_API_KEY}',  # 身份验证头
            'Content-Type': 'application/json',  # 数据格式声明
            'Accept': 'application/json'  # 期望的响应格式
        },
        data=json.dumps(json_data, ensure_ascii=False)  # 将字典转换为JSON字符串
    )

    return resp


def post_stream(json_data: Dict, tracker = None):
    resp = post(json_data)
    for item in resp.iter_lines():

        item_data = item.decode('utf-8')
        print(item_data)
        if item_data not in {'', None, 'data: [DONE]'}:
            print(item_data)
            item_data = json.loads(item_data[6:])
            content = item_data.get("choices")[0].get("delta").get("content")
            tracker.add_content(content)
        yield item
