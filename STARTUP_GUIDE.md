# 🚀 一键启动指南

## 快速开始

### 方案 1：一键启动（推荐）

**双击运行 `RUN.bat`**

```
RUN.bat
```

这将自动启动：
- ✅ Ollama 服务 (port 11434)
- ✅ FastAPI 后端 (port 8000)  
- ✅ Web UI (自动打开浏览器)

---

## 系统状态

启动完成后，脚本会显示：
- Ollama 服务状态
- FastAPI 服务状态
- 数据库状态 (3153 条对话)

---

## 关闭系统

**双击运行 `STOP.bat`**

```
STOP.bat
```

这将关闭：
- Ollama 服务
- FastAPI 后端

---

## 🔧 手动启动（高级）

如果需要查看详细日志，可手动启动：

### 终端 1：启动 Ollama
```powershell
$env:OLLAMA_MODELS = "D:\ai_model"
ollama serve
```

### 终端 2：启动 FastAPI
```powershell
python main.py
```

### 终端 3：打开浏览器
```
http://localhost:8000
```

---

## 📊 已导入数据

- **对话记录**：3,153 条
- **数据库文件**：`data/girlfriend.db` (336 KB)
- **AI 模型**：qwen:4b
- **API**：FastAPI (port 8000)

---

## ⚠️ 故障排除

### Ollama 无法启动
```powershell
# 检查进程
Get-Process ollama -ErrorAction SilentlyContinue

# 手动删除冲突进程
taskkill /F /IM ollama.exe
```

### FastAPI 无法启动
```powershell
# 检查 Python 虚拟环境
venv\Scripts\Activate.ps1

# 检查依赖
pip install -r requirements.txt
```

### 端口已被占用
```powershell
# 查看占用 8000 端口的进程
netstat -ano | findstr "8000"

# 查看占用 11434 端口的进程
netstat -ano | findstr "11434"
```

---

## 💡 常用命令

| 命令 | 说明 |
|------|------|
| `RUN.bat` | 启动完整系统 |
| `STOP.bat` | 关闭所有服务 |
| `python main.py` | 手动启动 FastAPI |
| `python import_wechat_data.py [文件]` | 导入微信数据 |

---

**最后更新**: 2026年2月24日
