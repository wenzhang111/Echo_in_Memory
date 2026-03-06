@echo off
chcp 65001 >nul
color 0C
cls

echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║              🛑 言忆 - 关闭所有服务                         ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

echo ⏳ 关闭服务中...
echo.

REM 关闭 FastAPI
echo [1/2] 关闭 FastAPI (port 8000)...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000"') do (
    taskkill /F /PID %%p >nul 2>&1
)
netstat -ano | findstr ":8000" >nul
if %errorlevel% neq 0 (
    echo ✓ FastAPI 已关闭
) else (
    echo ⚠️  FastAPI 仍在运行，请手动检查进程
)

REM 关闭 Ollama
echo [2/2] 关闭 Ollama (port 11434)...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":11434"') do (
    taskkill /F /PID %%p >nul 2>&1
)
taskkill /F /IM ollama.exe >nul 2>&1
netstat -ano | findstr ":11434" >nul
if %errorlevel% neq 0 (
    echo ✓ Ollama 已关闭
) else (
    echo ⚠️  Ollama 仍在运行，请手动检查进程
)

echo.
echo ✅ 所有服务已关闭
echo.
pause
