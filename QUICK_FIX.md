# 🚀 快速恢复步骤

## 现在的情况
1. ✅ Ollama 端口被占用（因为已经启动）
2. ⚠️ Web UI 显示 DeepSeek 401 错误（需要配置 API 密钥或使用 Ollama）
3. ⚠️ 有旧的相对导入错误提示（可以忽略，已修复）

---

## 方案 A：使用本地 Ollama（推荐，完全免费）

### 第 1 步：关闭旧的 Ollama 进程
```bash
kill_ollama.bat
```

### 第 2 步：一键启动系统（带 GPU 加速）
```bash
start.bat
选择 [1] 一键启动系统
```

系统会自动：
1. ✅ 关闭旧进程
2. ✅ 启动 Ollama（GPU 加速，CUDA/Intel GPU）
3. ✅ 启动 API 后端
4. ✅ 打开 Web UI

### 第 3 步：选择模型
- Web UI 顶部模型下拉菜单
- 选择 `🏠 本地(Ollama)` 
- 开始聊天！

**优点**：
- ✅ 完全免费
- ✅ 隐私保护（离线运行）
- ✅ 无需 API 密钥
- ✅ 支持 GPU 加速

**缺点**：
- ⏱️ 首次响应较慢（30-120秒）
- 💾 需要约 20GB 磁盘空间

---

## 方案 B：使用外部 API（快速但需密钥）

### 第 1 步：配置 API 密钥
```bash
setup_apis.bat
```

选择你要用的 API（推荐 DeepSeek，最便宜）：
```
[1] OpenAI (GPT-3.5/GPT-4) - 快速、强大
[2] DeepSeek - 极快、超便宜 ⭐ 推荐
[3] Claude - 高质量
```

### 第 2 步：启动系统
```bash
start.bat
选择 [1] 一键启动系统
```

### 第 3 步：在 Web UI 中选择模型
- 下拉菜单选择相应的 API 模型
- 即可快速获得回复（1-5秒）

---

## 方案 C：混合方案（最灵活）

同时运行 Ollama 和多个 API，系统自动选择最快的可用模型。

1. 运行 `kill_ollama.bat` 清理旧进程
2. 运行 `setup_apis.bat` 配置至少一个 API 密钥
3. 运行 `start.bat` 菜单选择 `[1]`
4. Web UI 会显示所有可用模型供选择

---

## 快速诊断

有问题？运行诊断工具：
```bash
diagnose.bat
```

它会检查：
- ✓ Python 环境
- ✓ 依赖安装
- ✓ Ollama 连接
- ✓ Web UI 文件
- ✓ API 密钥配置

---

## 脚本文件说明

| 脚本 | 功能 |
|------|------|
| `start.bat` | 主菜单，选择启动方式 |
| `kill_ollama.bat` | 关闭旧的 Ollama 进程 |
| `setup_apis.bat` | 配置 API 密钥 |
| `diagnose.bat` | 系统诊断工具 |
| `test_api_models.py` | Python 模型诊断脚本 |

---

## 关键改进（已在本次修复中进行）

✅ **Ollama 启动强制 GPU 加速**
```bat
set CUDA_VISIBLE_DEVICES=0
set OLLAMA_INTEL_GPU=1
ollama serve
```

✅ **自动清理旧进程**
```bat
taskkill /IM ollama.exe /F
```

✅ **改进的错误处理和日志**
- OpenAI/DeepSeek/Claude API 错误处理更完善
- 更详细的错误消息帮助诊断

✅ **相对导入错误已全部修复**
- `rag_system.py`: `from .database` → `from database`
- `memory_manager.py`: 相对导入转绝对导入
- `ollama_client.py`: Ollama 连接错误包装

---

## 下一步建议

### 立即尝试
1. 运行 `kill_ollama.bat`
2. 运行 `start.bat` → 选择 `[1]`
3. Web UI 中选择 `本地(Ollama)` 模型
4. 输入消息，享受本地 AI！

### 如需快速回复
1. 运行 `setup_apis.bat`
2. 配置 DeepSeek API 密钥（最便宜）
3. `start.bat` → 选择 `[1]`
4. Web UI 中选择 `DeepSeek` 模型
5. 1-5 秒内获得回复

---

**祝你使用愉快！** 🎉
