#!/usr/bin/env python3
"""测试 main.py 导入"""
import sys
from pathlib import Path

# 添加 src 目录到路径
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

try:
    print("[*] 正在导入 main.py...")
    from main import app
    print("✅ main.py 导入成功")
    print("✅ FastAPI 应用已准备好启动")
    print()
    print("系统状态:")
    print("  • 所有模块导入成功")
    print("  • 没有相对导入错误")
    print("  • 可以启动 API 后端")
    sys.exit(0)
except Exception as e:
    print(f"❌ 导入失败: {type(e).__name__}: {str(e)}")
    import traceback
    print("\n详细错误:")
    traceback.print_exc()
    sys.exit(1)
