#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试 Ollama 连接"""

import requests
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

print("=" * 60)
print("  🔍 Ollama 连接诊断")
print("=" * 60)

# 测试 Ollama API
try:
    print("\n[1/3] 测试 Ollama API 连接...")
    response = requests.get('http://localhost:11434/api/tags', timeout=5)
    print(f"✓ 收到响应，状态码: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        models = data.get('models', [])
        print(f"✓ Ollama 已连接")
        print(f"✓ 可用模型数: {len(models)}")
        for model in models[:5]:  # 显示前5个
            print(f"  - {model.get('name')}")
        if len(models) > 5:
            print(f"  ... 还有 {len(models) - 5} 个模型")
    else:
        print(f"✗ 返回错误状态码: {response.status_code}")
        
except requests.exceptions.ConnectionError:
    print("✗ 连接失败: 无法连接到 Ollama")
    print("   请确保 Ollama 服务正在运行: ollama serve")
except requests.exceptions.Timeout:
    print("✗ 连接超时: Ollama 响应缓慢")
except Exception as e:
    print(f"✗ 错误: {e}")

# 测试 FastAPI 的 Ollama 检测
print("\n[2/3] 测试 FastAPI 的 Ollama 检测...")
try:
    from ollama_client import chat_manager
    if chat_manager.ollama.check_connection():
        print("✓ FastAPI 可以连接到 Ollama")
    else:
        print("✗ FastAPI 无法连接到 Ollama")
except Exception as e:
    print(f"✗ 错误: {e}")

# 测试健康检查端点
print("\n[3/3] 测试 /health 端点...")
try:
    response = requests.get('http://localhost:8000/health')
    data = response.json()
    print(f"✓ 收到生活检查响应:")
    print(f"  - Status: {data.get('status')}")
    print(f"  - Ollama Connected: {data.get('ollama_connected')}")
    print(f"  - Conversations: {data.get('conversations')}")
except Exception as e:
    print(f"✗ 错误: {e}")
    
print("\n" + "=" * 60)
