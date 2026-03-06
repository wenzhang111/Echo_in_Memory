#!/bin/bash
# AI女友记忆系统 - Linux/Mac启动脚本

echo ""
echo "====================================="
echo "   AI女友记忆系统 - 启动脚本"
echo "====================================="
echo ""

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "[错误] Python未安装"
    echo "请运行: brew install python3 (Mac) 或 apt install python3 (Linux)"
    exit 1
fi

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "[信息] 虚拟环境不存在，正在创建..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 检查依赖
echo "[信息] 检查依赖..."
pip list | grep -i fastapi > /dev/null
if [ $? -ne 0 ]; then
    echo "[信息] 正在安装依赖..."
    pip install -r requirements.txt
fi

# 创建必要的目录
mkdir -p data logs embeddings

# 初始化数据库
if [ ! -f "data/girlfriend.db" ]; then
    echo "[信息] 初始化数据库..."
    python import_data.py sample 20
fi

# 显示使用说明
echo ""
echo "====================================="
echo ""
echo "[重要] 保持此窗口打开!"
echo ""
echo "在新的终端中运行以下命令来启动CLI:"
echo "  python cli.py"
echo ""
echo "或在浏览器中访问:"
echo "  http://localhost:8000/docs"
echo ""
echo "====================================="
echo ""
echo "[启动中...]"
echo ""

# 启动服务
python run_server.py
