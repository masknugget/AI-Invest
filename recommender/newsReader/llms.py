from typing import Optional

from openai import OpenAI


def chat_once(user_prompt: str, sys_prompt: Optional[str] = None) -> Optional[str]:
    client = OpenAI(
        # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key="sk-xxx"
        api_key=r'sk-d6e82744ac33451fbe0cff05687a3695',
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )

    if sys_prompt is None:
        messages = [
            {"role": "user", "content": user_prompt}
        ]
    else:
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt}
        ],

    completion = client.chat.completions.create(
        model="qwen-plus",
        # 此处以qwen-vl-plus为例，可按需更换模型名称。模型列表：https://help.aliyun.com/zh/model-studio/getting-started/models
        messages=messages,
    )

    resp = completion.choices[0].message.content
    return resp