import requests
import json

# 测试配置
BASE_URL = "http://localhost:8000"
CHAT_ENDPOINT = f"{BASE_URL}/api/chatbot/chat/completions"

# 测试用例1: 流式响应
def test_stream_chat():
    print("=== 测试流式响应 ===")
    payload = {
        "messages": [
            {"role": "user", "content": "你好，请介绍一下你自己"}
        ],
        "stream": True
    }
    
    try:
        response = requests.post(CHAT_ENDPOINT, json=payload, stream=True)
        response.raise_for_status()
        
        print("响应头:", dict(response.headers))
        print("流式内容:")
        
        for chunk in response.iter_lines(decode_unicode=True):
            if chunk:
                print(chunk.strip())
                
    except Exception as e:
        print(f"流式响应测试出错: {e}")


# 测试用例2: 非流式响应
def test_non_stream_chat():
    print("\n=== 测试非流式响应 ===")
    payload = {
        "messages": [
            {"role": "user", "content": "你好，请用一句话介绍Python"}
        ],
        "stream": False
    }
    
    try:
        response = requests.post(CHAT_ENDPOINT, json=payload)
        response.raise_for_status()
        
        result = response.json()
        print("完整响应:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        if "choices" in result and result["choices"]:
            content = result["choices"][0]["message"]["content"]
            print(f"\n助手回复: {content}")
            
    except Exception as e:
        print(f"非流式响应测试出错: {e}")


# 测试用例3: 错误情况 - 空消息
def test_empty_messages():
    print("\n=== 测试空消息错误 ===")
    payload = {
        "messages": [],
        "stream": False
    }
    
    try:
        response = requests.post(CHAT_ENDPOINT, json=payload)
        print(f"状态码: {response.status_code}")
        print(f"错误信息: {response.text}")
        
    except Exception as e:
        print(f"错误测试出错: {e}")


# 测试用例4: 多轮对话
def test_multi_turn_conversation():
    print("\n=== 测试多轮对话 ===")
    payload = {
        "messages": [
            {"role": "user", "content": "中国的首都是哪里？"},
            {"role": "assistant", "content": "中国的首都是北京。"},
            {"role": "user", "content": "那北京有什么著名景点？"}
        ],
        "stream": False
    }
    
    try:
        response = requests.post(CHAT_ENDPOINT, json=payload)
        response.raise_for_status()
        
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        print(f"助手回复: {content}")
        
    except Exception as e:
        print(f"多轮对话测试出错: {e}")


if __name__ == "__main__":
    print(f"测试接口: {CHAT_ENDPOINT}")
    print("确保服务已启动: uvicorn main:app --reload")
    print("=" * 60)
    
    test_stream_chat()
    test_non_stream_chat()
    test_empty_messages()
    test_multi_turn_conversation()
    
    print("\n=== 所有测试完成 ===")