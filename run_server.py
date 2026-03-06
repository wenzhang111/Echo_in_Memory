#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
言忆启动脚本
在项目根目录运行此脚本
"""
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

if __name__ == "__main__":
    # 导入FastAPI应用（从根目录）
    from main import app
    import uvicorn
    
    print("\n" + "="*60)
    print("  🚀 言忆 - FastAPI服务器")
    print("="*60)
    print("\n✓ 服务正在启动...")
    print("✓ API文档地址: http://localhost:8000/docs")
    print("✓ ReDoc文档地址: http://localhost:8000/redoc")
    print("\n")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
