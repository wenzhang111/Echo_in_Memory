#!/usr/bin/env python3
"""系统完整性检查"""

import subprocess
import time
import sys

print("=" * 70)
print("  🔍 AI女友系统完整性检查")
print("=" * 70)

checks = {
    "数据库": ["python", "-c", "import sqlite3; sqlite3.connect('data/girlfriend.db'); print('OK')"],
    "优化RAG": ["python", "-c", "from optimized_rag import optimized_rag; print('OK')"],
    "WebUI": ["python", "-c", "open('web_ui.html', encoding='utf-8').read(); print('OK')"],
    "依赖包": ["pip", "list", "--quiet"],
}

print("\n📋 检查清单:\n")

passed = 0
failed = 0

for name, cmd in checks.items():
    try:
        if name == "依赖包":
            result = subprocess.run(cmd, capture_output=True, timeout=10)
            if result.returncode == 0:
                print(f"OK {name:15} - 检查完成")
                passed += 1
            else:
                print(f"FAIL {name:15} - 检查失败")
                failed += 1
        else:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, encoding='utf-8')
            if "OK" in result.stdout or result.returncode == 0:
                print(f"OK {name:15} - 检查完成")
                passed += 1
            else:
                print(f"FAIL {name:15} - {result.stdout or result.stderr}")
                failed += 1
    except Exception as e:
        print(f"FAIL {name:15} - {str(e)}")
        failed += 1

print("\n" + "=" * 70)
print(f"RESULT: {passed} passed, {failed} failed")

if failed == 0:
    print("SUCCESS - All checks passed! System ready to launch")
    print("\nSTART OPTIONS:")
    print("   1. Double-click RUN.bat")
    print("   2. Or run: python main.py")
    print("=" * 70)
    sys.exit(0)
else:
    print("WARNING - Some checks failed, please fix and retry")
    print("=" * 70)
    sys.exit(1)
