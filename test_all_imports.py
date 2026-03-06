import sys
from database import db
print("[OK] database 导入成功")

from rag_system import rag_system
print("[OK] rag_system 导入成功")

from memory_manager import memory_extractor
print("[OK] memory_manager 导入成功")

from ollama_client import chat_manager
print("[OK] ollama_client 导入成功")

from api_models import model_manager
print("[OK] api_models 导入成功")

from main import app
print("[OK] main 导入成功")
print("[OK] FastAPI 应用已准备好启动")
