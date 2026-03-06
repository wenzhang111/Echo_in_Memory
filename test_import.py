#!/usr/bin/env python3
"""快速导入测试脚本"""
import sys
from pathlib import Path

# 进入 src 目录
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

try:
    from main import app
    print("✅ main.py 导入成功")
    print("✅ FastAPI 应用已准备好启动")
    print("\n下一步:")
    print("1. 启动 Ollama: ollama serve")
    print("2. 运行 API: python src\\main.py")
    print("3. 打开 Web UI: web_ui.html")
except Exception as e:
    print(f"❌ 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
