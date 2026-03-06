#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
完整的 Ollama 模型配置修复脚本
"""

import requests
import json
import time
import sys
import os
from pathlib import Path

def check_ollama():
    """检查 Ollama 是否在运行"""
    print("\n" + "=" * 70)
    print("  🔍 检查 Ollama 服务状态")
    print("=" * 70)
    
    try:
        r = requests.get('http://localhost:11434/api/tags', timeout=5)
        if r.status_code == 200:
            print("✓ Ollama 服务正在运行")
            return True
    except:
        pass
    
    print("❌ Ollama 服务未运行！\n")
    print("请按以下步骤操作：")
    print()
    print("【第 1 步】打开新的命令行窗口，运行启动脚本：")
    print("  Double-click 或运行：")
    print("  start_ollama_with_model_path.bat")
    print()
    print("【第 2 步】等待 Ollama 完全启动（看到 'Listening on' 消息）")
    print()
    print("【第 3 步】然后在这个窗口继续，再按 Enter 键")
    print()
    input("按 Enter 继续...")
    
    # 再检查一次
    try:
        r = requests.get('http://localhost:11434/api/tags', timeout=5)
        if r.status_code == 200:
            print("\n✓ Ollama 现在已连接！\n")
            return True
    except:
        pass
    
    print("\n❌ 仍然无法连接 Ollama，请检查启动脚本是否正确")
    return False


def get_model_list():
    """获取 Ollama 中的所有模型"""
    try:
        r = requests.get('http://localhost:11434/api/tags', timeout=5)
        if r.status_code == 200:
            models = r.json().get('models', [])
            return [m.get('name') for m in models]
    except:
        pass
    return []


def update_config(model_name):
    """更新 config.py 中的模型名称"""
    config_file = Path(__file__).parent / 'config.py'
    
    if not config_file.exists():
        print(f"❌ 找不到 {config_file}")
        return False
    
    content = config_file.read_text(encoding='utf-8')
    
    # 替换模型名称
    old_line = None
    for line in content.split('\n'):
        if line.strip().startswith('OLLAMA_MODEL'):
            old_line = line
            break
    
    if old_line:
        new_line = f'OLLAMA_MODEL = "{model_name}"  # 本地 Ollama 模型'
        content = content.replace(old_line, new_line)
        
        config_file.write_text(content, encoding='utf-8')
        print(f"✓ 已更新 config.py")
        print(f"  OLLAMA_MODEL = \"{model_name}\"")
        return True
    
    return False


def main():
    print("\n" + "=" * 70)
    print("  🚀 AI女友系统 - Ollama 模型配置修复")
    print("=" * 70)
    
    # 第 1 步：检查 Ollama
    if not check_ollama():
        print("\n❌ 无法连接到 Ollama，请检查启动脚本")
        return False
    
    # 第 2 步：获取模型列表
    print("\n" + "=" * 70)
    print("  📦 检查可用模型")
    print("=" * 70)
    
    models = get_model_list()
    
    if not models:
        print("\n❌ Ollama 中没有模型!")
        print("\n请运行以下命令之一来下载模型：")
        print("  ollama pull qwen:4b    (推荐，4GB)")
        print("  ollama pull qwen2:1b   (超快，1GB)")
        print("  ollama pull llama2:7b  (较强，7GB)")
        print("\n然后重新运行此脚本")
        return False
    
    print(f"\n✓ 找到 {len(models)} 个模型：\n")
    for i, model in enumerate(models, 1):
        print(f"  [{i}] {model}")
    
    # 第 3 步：让用户选择模型
    print("\n" + "=" * 70)
    print("  ⚙️  配置模型")
    print("=" * 70)
    
    if len(models) == 1:
        selected_model = models[0]
        print(f"\n✓ 自动选择唯一的模型: {selected_model}")
    else:
        print("\n请选择要使用的模型:")
        choice = input(f"输入数字 1-{len(models)} (默认=1): ").strip() or "1"
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(models):
                selected_model = models[idx]
            else:
                print("❌ 无效选择")
                return False
        except:
            print("❌ 输入错误")
            return False
    
    # 第 4 步：更新配置
    print("\n" + "=" * 70)
    print("  💾 保存配置")
    print("=" * 70)
    
    if update_config(selected_model):
        print("\n✅ 配置已更新！")
        print("\n现在可以：")
        print("  1. 启动 FastAPI: python run_server.py")
        print("  2. 访问 WebUI: http://localhost:8000")
        return True
    else:
        print("\n❌ 更新配置失败")
        return False


if __name__ == '__main__':
    success = main()
    
    print("\n" + "=" * 70)
    if success:
        print("✅ 配置完成！")
    else:
        print("❌ 配置失败，请检查上面的错误信息")
    print("=" * 70 + "\n")
    
    input("按 Enter 退出...")
