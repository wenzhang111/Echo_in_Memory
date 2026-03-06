# 言忆 (YanYi) — AI 记忆对话系统

<p align="center">
  <strong>🧠 会记忆 · 懂情绪 · 多角色 · 可进化</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.104+-green?logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/Ollama-本地推理-orange" alt="Ollama">
  <img src="https://img.shields.io/badge/License-MIT-yellow" alt="License">
</p>

---

言忆是一个多角色 AI 记忆对话系统，支持本地模型（Ollama）与外部 API（OpenAI / DeepSeek / Claude），具备：

- **长期记忆** — 自动提取、语义检索历史对话
- **情绪追踪** — 实时分析用户情绪曲线，AI 自适应回复策略
- **风格学习** — 从聊天记录自动学习表达习惯（口头禅、语气词、节奏）
- **多角色管理** — 每个角色独立人设、文风、聊天历史
- **意图感知** — 6 种意图分类 + 动态生成参数调优
- **结构化上下文** — Token 预算管理，不再溢出上下文窗口
- **回复增强** — 自动清理 thinking 标签、重复句、角色泄漏
- **主动对话** — 结合时间/话题发起开场白
- **一键启动** — `RUN.bat` 从环境部署到运行全自动

> 项目定位：把"聊天工具"升级成"可持续演化的人格工作台"。

---

## 📸 预览

启动后访问 `http://localhost:8000` 打开 Web UI，包含对话、角色管理、数据统计等功能。

---

## 🚀 快速开始

### 前置条件

- **Python 3.10+**
- **Ollama**（[下载](https://ollama.com/)）
- 一张 GPU（推荐 4GB+ 显存，CPU 也可运行但较慢）

### 一键启动（Windows 推荐）

```bat
双击 RUN.bat
```

脚本会自动：创建 venv → 安装依赖 → 检查 Ollama → 选择模型 → 启动服务 → 打开浏览器

停止服务：双击 `STOP.bat`

### 手动启动

```bash
# 1. 创建虚拟环境
python -m venv venv

# 2. 激活（Windows）
venv\Scripts\activate
# 或 Linux/Mac:
# source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 确保 Ollama 运行中
ollama serve

# 5. 拉取模型（首次）
ollama pull qwen:4b

# 6. 启动
python run_server.py
```

启动后：
- **Web UI**：http://localhost:8000
- **API 文档**：http://localhost:8000/docs

### 使用外部 API（可选）

复制 `.env.example` 为 `.env`，填入你的密钥：

```bash
cp .env.example .env
# 编辑 .env 填入 API Key
```

然后在 Web UI 的设置页切换到外部模型即可。

---

## 📁 项目结构

```text
ai-girlfriend-memory/
├─ main.py                 # FastAPI 主入口（REST API）
├─ web_ui.html             # 前端页面（对话/角色/数据管理）
├─ run_server.py           # 服务启动脚本
├─ RUN.bat / start.sh      # 一键启动
├─ STOP.bat                # 一键停止
│
├─ ollama_client.py        # Ollama 客户端 (/api/chat 结构化对话)
├─ api_models.py           # 外部 API 模型 (OpenAI/DeepSeek/Claude)
├─ config.py               # 全局配置
│
├─ context_engine.py       # Token 感知上下文构建器
├─ emotion_tracker.py      # 情绪曲线追踪 (valence-arousal 模型)
├─ response_enhancer.py    # 回复后处理 + 意图动态调参
├─ intent_classifier.py    # 意图分类器
│
├─ memory_manager.py       # 记忆管理（提取/检索/注入）
├─ rag_system.py           # 语义检索 (RAG)
├─ database.py             # SQLite 数据层
├─ character_manager.py    # 多角色管理
│
├─ style_learner.py        # 文风提取
├─ llm_style_extractor.py  # LLM 风格分析
├─ topic_initiator.py      # 主动话题发起
├─ daily_briefing.py       # 每日简报
├─ memory_compress.py      # 记忆压缩
│
├─ import_wechat_data.py   # 微信聊天记录导入工具
├─ requirements.txt        # Python 依赖
├─ .env.example            # 环境变量模板
└─ data/                   # 运行时数据（自动生成）
```

---

## 🧩 核心架构

```
用户输入
  │
  ├─→ 意图分类 (intent_classifier)
  │     └─→ 动态调参 (response_enhancer.get_dynamic_params)
  │
  ├─→ 情绪分析 (emotion_tracker)
  │     └─→ 生成情绪策略提示
  │
  ├─→ 记忆检索 (memory_manager + rag_system)
  │     └─→ 语义匹配相关历史
  │
  └─→ 上下文构建 (context_engine)
        └─→ Token 预算分配 → 结构化 messages[]
              │
              ├─→ Ollama /api/chat (本地)
              └─→ OpenAI/DeepSeek/Claude (外部 API)
                    │
                    └─→ 回复增强 (response_enhancer)
                          └─→ 清理 + 质量评分 → 返回用户
```

---

## 🎯 特性详解

### 意图动态调参

系统自动识别 6 种对话意图，并为每种意图配置最优生成参数：

| 意图 | 温度 | Max Tokens | 适用场景 |
|------|------|------------|----------|
| emotional_support | 0.85 | 600 | 情感倾诉、安慰 |
| relationship | 0.80 | 500 | 日常关系互动 |
| casual | 0.75 | 400 | 闲聊 |
| advice | 0.50 | 800 | 求建议 |
| planning | 0.40 | 600 | 规划、决策 |
| knowledge | 0.30 | 1000 | 知识问答 |

### 情绪追踪

- 60+ 中文情绪词库，基于 valence-arousal 模型
- 实时分析每轮用户情绪
- AI 回复前自动注入策略（低落→共情安慰，焦虑→引导放松）
- 提供情绪曲线 API 供前端可视化

### 回复增强流水线

```
原始输出 → 清除<think>标签 → 移除角色泄漏 → 去重复句 → 修剪截断 → 质量评分
```

### Token 预算管理

- system prompt ≤ 50% 预算
- 剩余空间动态分配给对话历史 + 当前输入
- 自动截断最老的历史轮次

---

## 📡 API 接口

### 对话

| 端点 | 方法 | 说明 |
|------|------|------|
| `/chat` | POST | 本地模型对话 |
| `/chat/stream` | GET | 本地模型流式 |
| `/chat-api` | POST | 外部模型对话 |
| `/chat-api/stream` | POST | 外部模型流式 (SSE) |

### 情绪

| 端点 | 方法 | 说明 |
|------|------|------|
| `/emotion/current` | GET | 实时分析文本情绪 |
| `/emotion/trend` | GET | 近期情绪走势 |
| `/emotion/curve` | GET | 情绪曲线数据 |

### 角色

| 端点 | 方法 | 说明 |
|------|------|------|
| `/characters` | GET/POST | 列出/创建角色 |
| `/characters/{id}` | PUT/DELETE | 更新/删除角色 |
| `/characters/{id}/activate` | POST | 切换活动角色 |

### 记忆与统计

| 端点 | 方法 | 说明 |
|------|------|------|
| `/memory/context` | GET | 当前记忆上下文 |
| `/memory/search` | GET | 语义搜索记忆 |
| `/history` | GET | 对话历史 |
| `/stats` | GET | 统计数据 |

### 风格与主动对话

| 端点 | 方法 | 说明 |
|------|------|------|
| `/style/learn` | POST | 从记录学习文风 |
| `/style/profile` | GET | 当前风格画像 |
| `/topic/suggest` | GET | 话题建议 |
| `/topic/proactive/trigger` | POST | 触发主动对话 |

完整 API 文档启动后访问：http://localhost:8000/docs

---

## ⚙️ 配置说明

### 模型选择

在 `RUN.bat` 启动时会自动列出本机 Ollama 模型，也可在 `config.py` 或环境变量中指定：

```bash
# 环境变量方式
set OLLAMA_MODEL=qwen2.5:7b
python run_server.py
```

推荐模型：
- **qwen:4b** — 4GB 显存，速度快（入门）
- **qwen3:8b** — 8GB 显存，效果好（推荐）
- **qwen2.5:14b** — 16GB 显存，高质量

### 上下文窗口

```bash
# 小模型建议 4000~6000，大模型可提高到 8000~12000
set MODEL_CONTEXT_WINDOW=6000
```

### GPU 配置

```bash
# 强制 GPU 推理
set OLLAMA_FORCE_GPU=1
set OLLAMA_NUM_GPU=999
```

---

## 📥 导入聊天记录

支持导入微信聊天记录以训练文风：

```bash
python import_wechat_data.py your_messages.json
```

导入后到 Web UI 角色页点击"**一键提取当前角色风格**"。

---

## ❓ 常见问题

**Q: Ollama 未连接？**
→ 先运行 `ollama serve`，再启动项目

**Q: 端口冲突（8000/11434）？**
→ 双击 `STOP.bat` 清理旧进程

**Q: 显存不足？**
→ 换小模型 `qwen:4b`，或设置 `OLLAMA_FORCE_GPU=0` 允许 CPU 回退

**Q: 新电脑迁移？**
→ 复制整个项目文件夹，双击 `RUN.bat` 自动部署

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建分支：`git checkout -b feature/your-feature`
3. 提交：`git commit -m 'feat: add your feature'`
4. 推送：`git push origin feature/your-feature`
5. 提交 PR

---

## 📄 License

[MIT License](LICENSE) — 自由使用，保留署名即可。

---

## 🙏 致谢

- [Ollama](https://ollama.com/) — 本地大模型推理
- [FastAPI](https://fastapi.tiangolo.com/) — Web 框架
- [sentence-transformers](https://www.sbert.net/) — 语义向量
- [Qwen](https://github.com/QwenLM/Qwen) — 推荐基座模型
