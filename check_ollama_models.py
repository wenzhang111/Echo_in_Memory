#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查 Ollama 模型"""

import requests
import json

print("检查 Ollama 可用模型...")
try:
    r = requests.get('http://localhost:11434/api/tags', timeout=5)
    if r.status_code == 200:
        models = r.json().get('models', [])
        print(f"✓ Ollama 已连接")
        print(f"✓ 可用模型数: {len(models)}")
        
        if len(models) == 0:
            print("\n⚠️ 没有安装任何模型！")
            print("请运行以下命令安装模型:")
            print("  ollama pull qwen:4b    # 推荐 (4GB)")
            print("  ollama pull qwen2:1b   # 超快 (1GB)")
            print("  ollama pull llama2:7b  # 较强 (7GB)")
        else:
            for m in models:
                print(f"  - {m.get('name')}")
    else:
        print(f"✗ Ollama 返回错误: {r.status_code}")
except Exception as e:
    print(f"✗ 无法连接: {e}")
