"""
配置文件 - AI女友记忆系统
"""
import os
from pathlib import Path

# ================== 项目路径 ==================
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "girlfriend.db"
EMBEDDINGS_DIR = PROJECT_ROOT / "embeddings"

# 确保目录存在
DATA_DIR.mkdir(exist_ok=True)
EMBEDDINGS_DIR.mkdir(exist_ok=True)

# ================== Ollama配置 ==================
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen:4b")  # 本地 Ollama 模型（可通过环境变量覆盖）
OLLAMA_TIMEOUT = 60  # 响应超时60秒
OLLAMA_TEMPERATURE = 0.7  # 生成温度
OLLAMA_TOP_P = 0.9
OLLAMA_FORCE_GPU = os.getenv("OLLAMA_FORCE_GPU", "1") == "1"  # 1=强制GPU, 0=允许CPU回退
OLLAMA_NUM_GPU = int(os.getenv("OLLAMA_NUM_GPU", "999"))  # Ollama num_gpu 参数，999 近似全GPU

# ================== 国内镜像配置 ==================
PIP_INDEX_URL = os.getenv("PIP_INDEX_URL", "https://pypi.tuna.tsinghua.edu.cn/simple")
HF_ENDPOINT = os.getenv("HF_ENDPOINT", "https://hf-mirror.com")

# ================== 外部API配置 ==================
# OpenAI 配置
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = "gpt-3.5-turbo"  # 可选: gpt-4-turbo（更强但更贵）

# DeepSeek 配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = "deepseek-chat"

# Claude 配置
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "")
CLAUDE_MODEL = "claude-3-sonnet-20240229"

# API 超时配置
API_REQUEST_TIMEOUT = 30  # 秒
API_MAX_RETRIES = 2  # 失败重试次数

# ================== GPU推理优化 ==================
# 生成参数优化（针对4060等低端GPU）
GENERATION_MAX_TOKENS = 256  # 从512改为256，加快生成速度
GENERATION_TOP_K = 30  # 从40改为30
GENERATION_NUM_PREDICT = 256  # 最大生成token数
GENERATION_REPEAT_PENALTY = 1.1  # 重复惩罚，提高多样性

# ================== 向量模型配置 ==================
# 使用轻量级中文embedding模型
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIMENSION = 384  # 向量维度

# ================== 上下文窗口配置 ==================
# Token预算：context_engine 会在此预算内自动分配 system/history/current
# 小模型(4b)建议4000~6000，大模型(8b+)可提高到8000~12000
MODEL_CONTEXT_WINDOW = int(os.getenv("MODEL_CONTEXT_WINDOW", "6000"))

# ================== 检索配置 ==================
# 检索相关对话时返回的最大条数
MAX_RETRIEVED_CONVERSATIONS = 10
# 向量相似度阈值（0-1）
SIMILARITY_THRESHOLD = 0.5
# 每次聊天包含的聊天历史轮数
CONTEXT_WINDOW = 5

# ================== 记忆提取配置 ==================
# 定期提取长期记忆的频率（每N条新对话）
MEMORY_EXTRACTION_FREQUENCY = 50
# 长期记忆库最大条目数
MAX_LONG_TERM_MEMORIES = 200
# 性格特征更新频率（每N条新对话）
PERSONALITY_UPDATE_FREQUENCY = 100

# ================== AI人设配置 ==================
AI_NAME = "萌萌"
AI_AGE = "24"
AI_OCCUPATION = "自由插画师"
AI_PERSONALITY_DESCRIPTION = "温柔体贴、略带调皮、爱撒娇但不做作"

# ================== FastAPI配置 ==================
API_HOST = "0.0.0.0"
API_PORT = 8000
API_DEBUG = True

# ================== 请求超时配置 ==================
CHAT_REQUEST_TIMEOUT = 180  # 聊天请求超时（秒）

# ================== 数据库配置 ==================
# SQLite设置
DB_CONN_TIMEOUT = 30

# ================== 日志配置 ==================
LOG_LEVEL = "INFO"
LOG_FILE = PROJECT_ROOT / "logs" / "app.log"
LOG_FILE.parent.mkdir(exist_ok=True)
