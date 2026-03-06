# 🔧 快速故障排除指南

## 问题 1: Ollama 端口被占用
**症状**: 启动时报错 `bind: Only one usage of each socket address`

**原因**: Ollama 进程仍在后台运行

**解决方案**:
```bash
# 方式 1：运行关闭脚本
kill_ollama.bat

# 方式 2：手动关闭
taskkill /IM ollama.exe /F
```

---

## 问题 2: Web UI 中出现 DeepSeek API 401 错误
**症状**: 聊天返回 `API 错误: Client error '401 Unauthorized'`

**原因**: 没有配置 DeepSeek API 密钥，或密钥不正确

**解决方案**:

### 方式 A：使用本地 Ollama（推荐 ✅）
- 启动系统选择 `[1]` 一键启动
- Web UI 中模型下拉菜单选择 `本地(Ollama)`
- 完全免费，无需 API 密钥

### 方式 B：配置 API 密钥
1. 运行 `setup_apis.bat`
2. 选择 `[2] DeepSeek` 配置密钥
3. 获取 API 密钥：https://platform.deepseek.com
4. 粘贴密钥，保存配置

---

## 问题 3: Web UI 显示"相对导入"错误
**症状**: 浏览器显示 `attempted relative import with no known parent package`

**原因**: 浏览器缓存或旧错误信息

**解决方案**:

### 方式 1：清除缓存
```
Ctrl + Shift + Delete
选择 "缓存的图像和文件"
点击 "清除数据"
```

### 方式 2：隐私窗口
```
Ctrl + Shift + N （新建隐私窗口）
访问 Web UI
```

### 方式 3：重新启动
```
1. 关闭所有浏览器窗口
2. 关闭 API 后端 (Ctrl+C)
3. 重新运行 start.bat 选择 [1]
```

---

## 问题 4: 第一次启动很慢
**症状**: 第一条消息需要 30-60 秒才能回复

**原因**: Ollama 模型首次加载到 GPU/内存中

**解决方案**:
- 等待第一条消息完成（这是一次性的）
- 后续消息会快得多
- 如果仍然很慢，使用 API 模型（需配置密钥）

---

## 问题 5: API 服务无法启动
**症状**: 点击 `[3] 仅启动 API` 后没有反应

**原因**: Ollama 服务未运行

**解决方案**:
```bash
# 在另一个终端先启动 Ollama
# 菜单选择 [2] 仅启动 Ollama 本地模型

# 然后在第一个终端启动 API
# 菜单选择 [3] 仅启动 API 后端
```

---

## 完整诊断
如果以上都不能解决，运行诊断工具：
```bash
diagnose.bat
```

---

## 环境变量配置 (高级)

如果想自定义配置，编辑系统环境变量：

```
OPENAI_API_KEY=sk-xxxxx...
DEEPSEEK_API_KEY=sk-xxxxx...
CLAUDE_API_KEY=sk-xxxxx...
OLLAMA_MODEL=qwen3:4b
OLLAMA_API_URL=http://localhost:11434/api/generate
```

---

## 技术支持
- **Ollama 官网**: https://ollama.ai
- **DeepSeek API**: https://platform.deepseek.com
- **OpenAI API**: https://platform.openai.com
- **Claude API**: https://www.anthropic.com

---

**最后更新**: 2026-02-23  
**版本**: 1.2.0
