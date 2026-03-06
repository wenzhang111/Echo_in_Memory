#!/usr/bin/env python3
"""
测试所有 API 大模型配置
检查密钥、连接、请求格式等问题
"""
import sys
import os
from pathlib import Path
import asyncio

# 添加项目目录
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root))

# 更改到 src 目录运行
os.chdir(str(project_root / "src"))

from api_models import model_manager

async def test_models():
    """测试所有可用模型"""
    print("\n" + "=" * 70)
    print("  AI女友系统 - API 大模型诊断工具")
    print("=" * 70 + "\n")
    
    # 1. 检查模型加载
    print("[1/3] 检查模型加载...")
    print("-" * 70)
    
    all_models = {}
    for name, model in model_manager.models.items():
        info = model.get_info()
        available = model.is_available()
        status = "✅ 可用" if available else "❌ 不可用"
        
        print(f"\n{status} {info['name']} ({name})")
        print(f"   模型: {info['model']}")
        print(f"   供应商: {info['provider']}")
        print(f"   速度: {info.get('speed', '未知')}")
        
        all_models[name] = (model, available)
    
    # 2. 获取可用模型列表
    print("\n" + "-" * 70)
    print("[2/3] 获取可用模型列表...")
    print("-" * 70 + "\n")
    
    available = model_manager.get_available_models()
    if available:
        print(f"✅ 找到 {len(available)} 个可用模型:\n")
        for item in available:
            print(f"   • {item['id']}")
    else:
        print("❌ 未找到任何可用模型")
        print("   请配置至少一个 API 密钥:")
        print("   • OPENAI_API_KEY (OpenAI)")
        print("   • DEEPSEEK_API_KEY (DeepSeek)")
        print("   • CLAUDE_API_KEY (Claude)")
        print("   或启动 Ollama 服务")
    
    # 3. 测试模型调用
    if available:
        print("\n" + "-" * 70)
        print("[3/3] 测试模型调用...")
        print("-" * 70 + "\n")
        
        test_message = "你好，请简短回答"
        
        for item in available[:2]:  # 只测试前两个模型
            model_name = item['id']
            print(f"\n🧪 测试 {model_name}...")
            
            try:
                response = await model_manager.generate(
                    message=test_message,
                    model_name=model_name,
                    context="",
                    temperature=0.7,
                    max_tokens=100
                )
                
                if response:
                    print(f"   ✅ 成功! 回复长度: {len(response)} 字符")
                    print(f"   回复内容: {response[:50]}...")
                else:
                    print(f"   ❌ 返回空回复")
                    
            except ValueError as e:
                print(f"   ❌ 错误: {str(e)}")
            except Exception as e:
                print(f"   ❌ 意外错误: {type(e).__name__}: {str(e)}")
    
    # 4. 检查环境变量
    print("\n" + "-" * 70)
    print("环境变量检查:")
    print("-" * 70 + "\n")
    
    env_vars = {
        "OPENAI_API_KEY": "OpenAI",
        "DEEPSEEK_API_KEY": "DeepSeek",
        "CLAUDE_API_KEY": "Claude",
        "OLLAMA_API_URL": "Ollama 服务地址",
        "OLLAMA_MODEL": "Ollama 模型名"
    }
    
    for env_key, description in env_vars.items():
        value = os.getenv(env_key, "")
        if value:
            masked = value[:10] + "***" if len(value) > 10 else value
            print(f"✅ {env_key:20} = {masked}")
        else:
            print(f"❌ {env_key:20} (未配置)")
    
    print("\n" + "=" * 70)
    print("诊断完成!")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    try:
        asyncio.run(test_models())
    except Exception as e:
        print(f"\n❌ 诊断脚本错误: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
