# 言忆

言忆是一个多角色 AI 记忆对话系统，支持本地模型（Ollama）与外部 API 模型，具备长期记忆、风格提取、分角色数据管理和主动话题发起能力。

项目目标：把“聊天工具”升级成“可持续演化的人格工作台”。

## 1. 核心能力

1. 多角色管理：每个角色独立人设、文风、聊天历史、统计。
2. 长期记忆系统：自动提取并检索历史对话，支持语义召回。
3. 风格提取学习：从聊天记录自动学习口头禅、语气词、表达节奏。
4. 主动对话发起：结合时间/天气/近期话题，生成主动开场。
5. 本地优先：支持纯本地 Ollama 运行，隐私可控。
6. 一键启动：`RUN.bat` 支持从环境部署到运行的完整流程。

## 2. 项目结构

```text
ai-girlfriend-memory/
├─ main.py                # FastAPI 主入口
├─ web_ui.html            # 前端页面（功能总览 + 对话 + 角色 + 数据管理）
├─ run_server.py          # 服务启动脚本
├─ RUN.bat                # 一键部署并启动
├─ STOP.bat               # 一键停止
├─ database.py            # 数据库层
├─ memory_manager.py      # 记忆管理
├─ rag_system.py          # 语义检索
├─ optimized_rag.py       # 记忆检索优化
├─ style_learner.py       # 风格提取
├─ llm_style_extractor.py # LLM 风格分析
├─ topic_initiator.py     # 主动话题
├─ api_models.py          # 外部 API 模型
├─ ollama_client.py       # Ollama 客户端
├─ config.py              # 配置
├─ requirements.txt       # 依赖
└─ data/                  # 数据目录（含 data/girlfriend.db）
```

## 3. 一键化部署与启动（推荐）

直接双击 `RUN.bat`，脚本会自动执行以下步骤：

1. 检查 Python。
2. 自动创建 `venv`（若不存在）。
3. 自动安装/校验依赖（`pip install -r requirements.txt`）。
4. 检查并拉起 Ollama 服务。
5. 自动列出你本机已有 Ollama 模型，并允许你选择。
6. 以选定模型启动 FastAPI。
7. 自动打开 Web UI。

启动后访问：

- Web UI：`http://localhost:8000`
- API 文档：`http://localhost:8000/docs`

停止服务：双击 `STOP.bat`。

## 4. 模型选择说明

### 4.1 在 RUN.bat 中选择现有模型

`RUN.bat` 会读取 `ollama list` 并展示本机模型列表，你可输入模型名切换。

输入后脚本会先校验模型是否存在；若不存在，会询问是否自动 `ollama pull`。

示例：

- `qwen:4b`
- `qwen2.5:7b`
- `llama3:8b`

如果本机没有模型，脚本会提示自动拉取默认模型 `qwen:4b`。

### 4.2 固定默认模型（可选）

在 `config.py` 中：

```python
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen:4b")
```

或手动设置环境变量后启动：

```bat
set OLLAMA_MODEL=qwen2.5:7b
python run_server.py
```

## 5. WebUI 操作指南

### 5.1 功能总览

首页“功能总览”会集中展示所有能力，并提供快捷按钮。

### 5.2 推荐流程

1. 导入聊天记录（导入页）。
2. 在角色页点击“**一键提取当前角色风格**”。
3. 回到对话页开始聊天。
4. 在设置页使用“分角色数据管理”导出/清理。

### 5.3 分角色数据管理

设置页支持数据范围切换：

- 当前角色
- 全部角色

并提供：

- 刷新统计
- 导出历史
- 导出记忆
- 按范围清理会话
- 全库清空

## 6. API 关键接口

### 对话

- `POST /chat`（本地模型）
- `GET /chat/stream`（本地流式）
- `POST /chat-api`（外部模型）
- `POST /chat-api/stream`（外部流式）

### 角色

- `GET /characters`
- `POST /characters`
- `PUT /characters/{char_id}`
- `DELETE /characters/{char_id}`
- `POST /characters/{char_id}/activate`

### 记忆与统计

- `GET /memory/context`
- `GET /memory/search`
- `GET /memory/all?emotion_priority=true`（情感优先重排）
- `POST /memory/correct-priority`（高优先纠错通道）
- `POST /memory/compact`
- `POST /memory/decay`
- `GET /history`
- `GET /history/related`
- `GET /stats`
- `GET /stats/optimized`

### 风格与主动对话

- `POST /style/learn`
- `GET /style/profile`
- `PUT /style/control`（风格强度档位 + 负向约束）
- `GET /topic/suggest`
- `POST /topic/proactive/trigger`

### 功能助手（模块化）

- `GET /assistant/skills`（查看已注册技能）
- `POST /assistant/execute`（统一执行技能）
- `POST /assistant/suggest`（根据输入推荐技能）

内置技能（可扩展）：
- `topic_suggestion` 话题建议
- `daily_briefing` 每日通报
- `intent_detect` 意图识别
- `emotion_snapshot` 情绪快照
- `anniversary_upcoming` 纪念日提醒
- `memory_snapshot` 记忆摘要

扩展方式：在 `assistant_skills.py` 中新增 `AssistantSkill` 并注册到 `FunctionalAssistantHub`。

### 评估

- `GET /metrics/summary`（记忆命中率/误召回率/纠错率 + 风格相似度/一致性/满意度代理）

## 6.1 桌宠（增强版）

Web UI 内置一个轻量桌宠（右下角悬浮）：

- 可拖拽
- 吸边停靠（拖拽释放后自动贴边）
- 自动巡游（可在桌宠菜单开关）
- 状态机动画（待机/巡游/思考/睡眠）
- 单击随机鼓励文案，双击快速调用助手技能生成话题建议
- 右键菜单快捷动作（生成话题、今日通报、跳转聊天、缩放、开关气泡）
- 本地持久化桌宠设置（位置/缩放/开关）

### 管理

- `GET /admin/conversation-summary`
- `DELETE /admin/clear-conversations`
- `POST /admin/clear`

## 7. 手动启动（非一键）

```bat
cd c:\Users\HP\Desktop\ai-girlfriend-memory
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
ollama serve
python run_server.py
```

## 8. 常见问题

### Q1: 页面显示 Ollama 未连接

先执行：

```bat
ollama serve
```

然后重新运行 `RUN.bat`。

### Q2: 端口冲突（8000/11434）

双击 `STOP.bat` 清理，再重新启动。


## 作者的碎碎念

这个项目最初的开发目的其实是为了回忆一个可能永远无法再和我聊天的女孩。现实生活中，我们总在错过着许多人，通过这个项目希望能让你通过聊天记录与他们再次建立联系。
当然我还是更希望每个用户都能在现实中不再错过，如果有什么想对这个人说，希望能抛弃自己的胆怯，在现实中去寻找那个真实的她。
如果是已经无法再见的人，希望也能让你在这个没有再见机会的现实世界走下去。
