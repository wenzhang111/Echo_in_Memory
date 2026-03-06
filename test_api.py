#!/usr/bin/env python3
"""测试 FastAPI 是否正常运行"""

import requests
import json
import time

def test_api():
    try:
        # 测试健康检查
        print("🔍 测试 FastAPI 服务...\n")
        resp = requests.get('http://localhost:8000/health', timeout=5)
        print(f'✅ FastAPI 服务状态: {resp.status_code}')
        print(f'   响应: {resp.json()}')
        
        # 测试对话端点
        print(f'\n📊 测试对话功能...')
        
        # 测试一个简单的聊天请求
        chat_data = {
            "message": "你好，今天怎么样？",
            "model": "qwen:4b"
        }
        
        resp = requests.post(
            'http://localhost:8000/chat',
            json=chat_data,
            timeout=30
        )
        
        if resp.status_code == 200:
            result = resp.json()
            print(f'   ✅ 聊天成功!')
            print(f'   用户消息: {chat_data["message"]}')
            print(f'   AI回复: {result.get("response", "")[:100]}...')
            print(f'   使用的上下文: {result.get("context_messages", 0)} 条')
        else:
            print(f'   ❌ 聊天失败: {resp.status_code}')
            print(f'   错误: {resp.text}')
        
    except requests.exceptions.ConnectionError:
        print(f'❌ 无法连接到 FastAPI 服务')
        print(f'\n💡 请先启动服务:')
        print(f'   python main.py')
        return False
    except Exception as e:
        print(f'❌ 错误: {e}')
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == '__main__':
    test_api()
