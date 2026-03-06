@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
color 0B
cls

echo.
echo ============================================================
echo 言忆 - 一键启动器
echo 环境部署 + 模型选择 + 服务启动 全自动流程
echo ============================================================
echo.

cd /d "%~dp0"

set "PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple"
set "HF_ENDPOINT=https://hf-mirror.com"
set "OLLAMA_FORCE_GPU=1"
set "OLLAMA_NUM_GPU=999"

echo [1/7] 检查 Python...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 未检测到 Python，请先安装 Python 3.10+ 并加入 PATH
    pause
    exit /b 1
)

echo [2/7] 准备虚拟环境...
if not exist "venv\Scripts\activate.bat" (
    echo    未检测到 venv，正在自动创建...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] 创建虚拟环境失败
        pause
        exit /b 1
    )
)
call venv\Scripts\activate.bat

echo [3/7] 安装/校验依赖...
echo    使用国内 pip 镜像: !PIP_INDEX_URL!
python -m pip install --upgrade pip --disable-pip-version-check -i "!PIP_INDEX_URL!" >nul 2>&1
python -m pip install -r requirements.txt --disable-pip-version-check -i "!PIP_INDEX_URL!"
if %errorlevel% neq 0 (
    echo [ERROR] 依赖安装失败，请检查网络或 requirements.txt
    pause
    exit /b 1
)

echo [4/7] 检查 Ollama...
where ollama >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 未检测到 Ollama，请先安装: https://ollama.com/download
    pause
    exit /b 1
)

curl.exe -s http://127.0.0.1:11434/api/tags >nul 2>&1
if %errorlevel% neq 0 (
    echo    Ollama 未运行，正在后台启动...
    start "Ollama" /D "%~dp0" cmd /K "ollama serve"
) else (
    echo    [OK] Ollama 已运行
)

set /a OLLAMA_WAIT_MAX=60
set /a OLLAMA_WAIT_COUNT=0
echo    等待 Ollama 就绪（最长 !OLLAMA_WAIT_MAX! 秒）...

:WAIT_OLLAMA_READY
curl.exe -s http://127.0.0.1:11434/api/tags >nul 2>&1
if !errorlevel! equ 0 goto OLLAMA_READY

set /a OLLAMA_WAIT_COUNT+=1
if !OLLAMA_WAIT_COUNT! geq !OLLAMA_WAIT_MAX! (
    echo [ERROR] Ollama 启动超时，请稍后重试或手动执行 ollama serve
    pause
    exit /b 1
)
timeout /t 1 /nobreak >nul
goto WAIT_OLLAMA_READY

:OLLAMA_READY
echo    [OK] Ollama 已就绪（等待 !OLLAMA_WAIT_COUNT! 秒）

echo [5/7] 选择本机 Ollama 模型...
set "FIRST_MODEL="
set /a MODEL_COUNT=0
for /f "skip=1 tokens=1" %%m in ('ollama list 2^>nul') do (
    if not "%%m"=="" (
        if not defined FIRST_MODEL set "FIRST_MODEL=%%m"
        set /a MODEL_COUNT+=1
        echo    - %%m
    )
)

if !MODEL_COUNT! equ 0 (
    echo    未检测到任何本地模型。
    set "FIRST_MODEL=qwen:4b"
    set /p "AUTO_PULL=是否自动拉取默认模型 qwen:4b ? [Y/n]: "
    if /I "!AUTO_PULL!"=="n" (
        echo 请手动执行: ollama pull ^<模型名^>，然后重试 RUN.bat
        pause
        exit /b 1
    )
    ollama pull qwen:4b
    if %errorlevel% neq 0 (
        echo [ERROR] 默认模型拉取失败，请手动执行 ollama pull qwen:4b
        pause
        exit /b 1
    )
)

if not defined FIRST_MODEL set "FIRST_MODEL=qwen:4b"
set "SELECTED_MODEL=!FIRST_MODEL!"
echo.
set /p "INPUT_MODEL=请输入要使用的模型名（回车默认 !FIRST_MODEL!）: "
if not "!INPUT_MODEL!"=="" set "SELECTED_MODEL=!INPUT_MODEL!"

ollama show "!SELECTED_MODEL!" >nul 2>&1
if !errorlevel! neq 0 (
    echo    未检测到模型: !SELECTED_MODEL!
    set /p "PULL_MISSING=是否自动拉取该模型? [Y/n]: "
    if /I "!PULL_MISSING!"=="n" (
        echo 请手动执行: ollama pull !SELECTED_MODEL!
        pause
        exit /b 1
    )
    ollama pull "!SELECTED_MODEL!"
    if !errorlevel! neq 0 (
        echo [ERROR] 模型拉取失败，请检查网络或模型名称
        pause
        exit /b 1
    )
)

set "OLLAMA_MODEL=!SELECTED_MODEL!"
echo    [OK] 当前模型: !OLLAMA_MODEL!

echo    预热模型并检查 GPU 运行状态...
curl.exe -s -H "Content-Type: application/json" -d "{\"model\":\"!OLLAMA_MODEL!\",\"prompt\":\"你好\",\"stream\":false,\"options\":{\"num_gpu\":!OLLAMA_NUM_GPU!,\"num_predict\":8}}" http://127.0.0.1:11434/api/generate >nul 2>&1

if "!OLLAMA_FORCE_GPU!"=="1" (
    ollama ps | findstr /I "!OLLAMA_MODEL!" | findstr /I "GPU" >nul 2>&1
    if !errorlevel! neq 0 (
        echo [ERROR] 检测到当前模型未运行在 GPU 上，已按强制GPU策略中止启动
        echo         可执行 "ollama ps" 查看 PROCESSOR 列
        echo         如需允许CPU回退，请将 RUN.bat 中 OLLAMA_FORCE_GPU 改为 0
        pause
        exit /b 1
    )
)

echo [6/7] 启动 FastAPI...
start "Yanyi-FastAPI" /D "%~dp0" cmd /K "call venv\Scripts\activate.bat && set OLLAMA_MODEL=!OLLAMA_MODEL! && set OLLAMA_FORCE_GPU=!OLLAMA_FORCE_GPU! && set OLLAMA_NUM_GPU=!OLLAMA_NUM_GPU! && set HF_ENDPOINT=!HF_ENDPOINT! && python run_server.py"

set /a API_WAIT_MAX=45
set /a API_WAIT_COUNT=0
echo    等待 FastAPI 就绪（最长 !API_WAIT_MAX! 秒）...

:WAIT_API_READY
curl.exe -s -o NUL -w "%%{http_code}" http://127.0.0.1:8000/health | findstr "200" >nul 2>&1
if !errorlevel! equ 0 goto API_READY

set /a API_WAIT_COUNT+=1
if !API_WAIT_COUNT! geq !API_WAIT_MAX! (
    echo [ERROR] FastAPI 启动超时，请查看 "Yanyi-FastAPI" 终端窗口中的报错信息
    pause
    exit /b 1
)
timeout /t 1 /nobreak >nul
goto WAIT_API_READY

:API_READY
echo    [OK] FastAPI 已就绪（等待 !API_WAIT_COUNT! 秒）

echo [7/7] 打开 Web UI...
start "" http://localhost:8000

echo.
echo ============================================================
echo 启动完成
echo Web UI:   http://localhost:8000
echo API文档:  http://localhost:8000/docs
echo 当前模型: !OLLAMA_MODEL!
echo 关闭服务: 双击 STOP.bat
echo ============================================================
echo.
pause
