#!/usr/bin/env python3
"""
Ollama 诊断工具 - 检查和启动 Ollama 服务
"""
import requests
import json
import subprocess
import time
import sys
from pathlib import Path

try:
    from config import OLLAMA_API_URL, OLLAMA_MODEL
except ImportError:
    OLLAMA_API_URL = "http://localhost:11434/api/generate"
    OLLAMA_MODEL = "qwen:7b"


class OllamaDiagnostics:
    def __init__(self):
        self.base_url = OLLAMA_API_URL.replace('/api/generate', '')
        self.model = OLLAMA_MODEL
        self.colors = {
            'red': '\033[91m',
            'green': '\033[92m',
            'yellow': '\033[93m',
            'blue': '\033[94m',
            'end': '\033[0m'
        }
    
    def print_color(self, text, color='blue'):
        print(f"{self.colors.get(color, '')}{text}{self.colors['end']}")
    
    def check_connection(self):
        """检查 Ollama 连接"""
        self.print_color("\n[1] 检查 Ollama 服务连接...", 'blue')
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=3)
            if response.status_code == 200:
                self.print_color("✓ Ollama 服务已启动", 'green')
                return True
        except requests.exceptions.ConnectionError:
            self.print_color("✗ 无法连接到 Ollama（连接被拒绝）", 'red')
            self.print_color("  → Ollama 可能未启动", 'yellow')
        except Exception as e:
            self.print_color(f"✗ 连接错误: {e}", 'red')
        
        return False
    
    def check_models(self):
        """检查可用模型"""
        self.print_color("\n[2] 检查可用模型...", 'blue')
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                models = data.get('models', [])
                
                if not models:
                    self.print_color("✗ 没有找到任何模型", 'red')
                    self.print_color(f"  → 请运行: ollama pull {self.model}", 'yellow')
                    return False
                else:
                    self.print_color(f"✓ 找到 {len(models)} 个模型:", 'green')
                    for model in models:
                        model_name = model.get('name', 'unknown')
                        size = model.get('size', 0) / (1024**3)
                        self.print_color(f"  - {model_name} ({size:.2f}GB)", 'green')
                    
                    # 检查指定的模型是否存在
                    model_names = [m.get('name', '') for m in models]
                    if any(self.model in name for name in model_names):
                        self.print_color(f"✓ 目标模型 '{self.model}' 已加载", 'green')
                        return True
                    else:
                        self.print_color(f"✗ 目标模型 '{self.model}' 未找到", 'red')
                        self.print_color(f"  → 请运行: ollama pull {self.model}", 'yellow')
                        return False
        except Exception as e:
            self.print_color(f"✗ 检查模型失败: {e}", 'red')
            return False
    
    def test_api_call(self):
        """测试 API 调用"""
        self.print_color("\n[3] 测试 API 调用...", 'blue')
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": "说一个笑话",
                    "stream": False
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('response'):
                    self.print_color("✓ API 调用成功", 'green')
                    self.print_color(f"  回复: {result['response'][:100]}...", 'green')
                    return True
            else:
                self.print_color(f"✗ API 返回错误代码: {response.status_code}", 'red')
                self.print_color(f"  响应: {response.text}", 'red')
        except Exception as e:
            self.print_color(f"✗ API 调用失败: {e}", 'red')
        
        return False
    
    def run_full_diagnosis(self):
        """运行完整诊断"""
        self.print_color("\n" + "="*50, 'blue')
        self.print_color("Ollama 诊断工具", 'blue')
        self.print_color("="*50, 'blue')
        
        self.print_color(f"\n配置信息:", 'blue')
        self.print_color(f"  API URL: {self.base_url}", 'yellow')
        self.print_color(f"  模型: {self.model}", 'yellow')
        
        results = {
            '连接': self.check_connection(),
            '模型': self.check_models(),
        }
        
        if results['连接'] and results['模型']:
            results['API'] = self.test_api_call()
        else:
            self.print_color("\n⚠ 跳过 API 测试（没有连接或模型）", 'yellow')
        
        # 总结
        self.print_color("\n" + "="*50, 'blue')
        self.print_color("诊断总结", 'blue')
        self.print_color("="*50, 'blue')
        
        all_pass = all(results.values())
        if all_pass:
            self.print_color("\n✓ 所有检查通过！系统已准备就绪。", 'green')
        else:
            self.print_color("\n✗ 检测到问题。请遵循上面的建议修复。", 'red')
            self.print_color("\n常见问题解决方案:", 'yellow')
            self.print_color("1. 启动 Ollama (如果未启动):", 'yellow')
            self.print_color("   Windows: 运行 Ollama 应用 或 ollama serve", 'yellow')
            self.print_color("   Linux/Mac: ollama serve", 'yellow')
            self.print_color("\n2. 下载模型:", 'yellow')
            self.print_color(f"   ollama pull {self.model}", 'yellow')
            self.print_color("\n3. 检查防火墙:", 'yellow')
            self.print_color("   确保允许本地 localhost:11434 连接", 'yellow')
        
        return all_pass


if __name__ == "__main__":
    diag = OllamaDiagnostics()
    success = diag.run_full_diagnosis()
    sys.exit(0 if success else 1)
