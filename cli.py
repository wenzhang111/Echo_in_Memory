#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
交互式CLI客户端 - 直接在终端与AI女友聊天
"""
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

import requests
import json
from datetime import datetime
from typing import Optional
import logging

logging.basicConfig(level=logging.WARNING)

# ANSI颜色代码
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class ChatClient:
    """CLI聊天客户端"""
    
    def __init__(self, api_url: str = "http://localhost:8000"):
        self.api_url = api_url
        self.session = requests.Session()
        self.conversation_count = 0
        self.check_connection()
    
    def check_connection(self) -> bool:
        """检查服务器连接"""
        try:
            response = self.session.get(f"{self.api_url}/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                status = data.get('status')
                online = data.get('ollama_connected')
                count = data.get('conversations', 0)
                
                print(f"{Colors.OKGREEN}✓ 服务器已连接{Colors.ENDC}")
                print(f"  状态: {status}")
                print(f"  Ollama: {'✓ 在线' if online else '✗ 离线'}")
                print(f"  对话数: {count}")
                
                self.conversation_count = count
                
                if not online:
                    print(f"{Colors.WARNING}⚠ Ollama离线，请运行: ollama serve{Colors.ENDC}")
                    return False
                
                return True
        
        except requests.ConnectionError:
            print(f"{Colors.FAIL}✗ 无法连接到服务器 ({self.api_url}){Colors.ENDC}")
            print(f"   请确保FastAPI服务正在运行: python src/main.py")
            return False
        
        except Exception as e:
            print(f"{Colors.FAIL}✗ 连接错误: {e}{Colors.ENDC}")
            return False
    
    def chat(self, message: str, use_memory: bool = True) -> Optional[str]:
        """发送消息并获取回复"""
        try:
            response = self.session.post(
                f"{self.api_url}/chat",
                json={
                    "message": message,
                    "use_memory": use_memory,
                    "temperature": 0.7,
                    "max_tokens": 512
                },
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                self.conversation_count = data.get('message_count', 0)
                return data.get('ai_response')
            else:
                print(f"{Colors.FAIL}错误: {response.status_code}{Colors.ENDC}")
                return None
        
        except requests.Timeout:
            print(f"{Colors.WARNING}⏱ 请求超时，模型生成太慢，请稍候...{Colors.ENDC}")
            return None
        except Exception as e:
            print(f"{Colors.FAIL}错误: {e}{Colors.ENDC}")
            return None
    
    def search_memory(self, keyword: str) -> Optional[dict]:
        """搜索相关记忆"""
        try:
            response = self.session.get(
                f"{self.api_url}/memory/search",
                params={"keyword": keyword},
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            return None
        
        except Exception as e:
            print(f"{Colors.FAIL}错误: {e}{Colors.ENDC}")
            return None
    
    def get_personality(self) -> Optional[str]:
        """获取性格档案"""
        try:
            response = self.session.get(
                f"{self.api_url}/personality",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('summary', '')
            return None
        
        except Exception as e:
            print(f"{Colors.FAIL}错误: {e}{Colors.ENDC}")
            return None
    
    def get_stats(self) -> Optional[dict]:
        """获取系统统计"""
        try:
            response = self.session.get(
                f"{self.api_url}/stats",
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            return None
        
        except Exception as e:
            print(f"{Colors.FAIL}错误: {e}{Colors.ENDC}")
            return None
    
    def show_help(self):
        """显示帮助信息"""
        help_text = f"""
{Colors.HEADER}{Colors.BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.ENDC}
{Colors.HEADER}{Colors.BOLD}     AI女友记忆系统 - 交互式CLI客户端{Colors.ENDC}
{Colors.HEADER}{Colors.BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.ENDC}

{Colors.OKGREEN}命令列表:{Colors.ENDC}
  {Colors.OKBLUE}/memory <关键词>{Colors.ENDC}    - 搜索相关的历史对话和记忆
  {Colors.OKBLUE}/personality{Colors.ENDC}        - 显示我的性格档案
  {Colors.OKBLUE}/stats{Colors.ENDC}             - 显示系统统计信息
  {Colors.OKBLUE}/clear{Colors.ENDC}            - 清空所有对话和记忆
  {Colors.OKBLUE}/help{Colors.ENDC}             - 显示帮助信息
  {Colors.OKBLUE}/quit{Colors.ENDC}             - 退出程序
  {Colors.OKBLUE}/nomem{Colors.ENDC}            - 下一条消息不使用记忆系统

{Colors.OKGREEN}用法示例:{Colors.ENDC}
  你: 你好，今天天气怎么样
  我: 天气真好呢~和你聊天心情也变好了 💕
  
  你: /memory 工作
  [显示相关的历史对话]
  
  你: /personality
  [显示我学到的性格特征]

{Colors.OKGREEN}提示:{Colors.ENDC}
  - 输入越多对话，我对你的了解就越深
  - 系统每50条新对话自动提取一次记忆
  - 使用 /memory 可以看我如何"记得"你的事

{Colors.HEADER}{Colors.BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.ENDC}
"""
        print(help_text)
    
    def run(self):
        """交互式聊天循环"""
        print(f"\n{Colors.OKCYAN}{Colors.BOLD}欢迎和我聊天！{Colors.ENDC}")
        print(f"输入 {Colors.OKBLUE}/help{Colors.ENDC} 查看命令列表\n")
        
        use_memory = True
        
        while True:
            try:
                user_input = input(f"{Colors.OKGREEN}你:{Colors.ENDC} ").strip()
                
                if not user_input:
                    continue
                
                # 处理命令
                if user_input.startswith('/'):
                    self.handle_command(user_input, use_memory)
                    if user_input == '/nomem':
                        use_memory = False
                    continue
                
                # 重置记忆标志
                if not use_memory:
                    use_memory = True
                    print(f"{Colors.WARNING}[本条消息不使用记忆系统]{Colors.ENDC}")
                
                # 发送消息
                print(f"{Colors.OKCYAN}我: 正在思考...{Colors.ENDC}", end='\r')
                
                response = self.chat(user_input, use_memory=use_memory)
                
                if response:
                    print(f"{Colors.OKCYAN}我:{Colors.ENDC} {response}\n")
                else:
                    print(f"{Colors.FAIL}生成回复失败，请重试{Colors.ENDC}\n")
            
            except KeyboardInterrupt:
                print(f"\n{Colors.WARNING}晚安~{Colors.ENDC}")
                break
            except Exception as e:
                print(f"{Colors.FAIL}错误: {e}{Colors.ENDC}")
    
    def handle_command(self, command: str, use_memory: bool = True):
        """处理命令"""
        if command == '/help':
            self.show_help()
        
        elif command.startswith('/memory '):
            keyword = command[8:].strip()
            if not keyword:
                print(f"{Colors.WARNING}请输入关键词{Colors.ENDC}")
                return
            
            print(f"{Colors.OKCYAN}搜索相关记忆中...{Colors.ENDC}")
            result = self.search_memory(keyword)
            
            if result and result.get('results'):
                print(f"\n{Colors.OKGREEN}找到 {len(result['results'])} 条相关记忆:{Colors.ENDC}")
                for i, mem in enumerate(result['results'][:5], 1):
                    print(f"{Colors.OKBLUE}  {i}. {Colors.ENDC}{mem.get('content', '')[:80]}")
            else:
                print(f"{Colors.WARNING}没有找到相关记忆{Colors.ENDC}")
            print()
        
        elif command == '/personality':
            print(f"{Colors.OKCYAN}正在加载我的性格档案...{Colors.ENDC}")
            personality = self.get_personality()
            
            if personality:
                print(f"\n{Colors.OKGREEN}{personality}{Colors.ENDC}\n")
            else:
                print(f"{Colors.WARNING}无法加载性格档案{Colors.ENDC}\n")
        
        elif command == '/stats':
            print(f"{Colors.OKCYAN}正在加载系统统计...{Colors.ENDC}")
            stats = self.get_stats()
            
            if stats:
                print(f"\n{Colors.OKGREEN}系统统计:{Colors.ENDC}")
                print(f"  总对话数: {stats.get('total_conversations', 0)}")
                print(f"  总记忆数: {stats.get('total_memories', 0)}")
                print(f"  性格特征: {stats.get('personality_traits', 0)}")
                print(f"  数据库大小: {stats.get('database_size_mb', 0):.2f} MB")
                print()
            else:
                print(f"{Colors.WARNING}无法加载统计信息{Colors.ENDC}\n")
        
        elif command == '/clear':
            confirm = input(f"{Colors.WARNING}确认清空所有数据？(yes/no): {Colors.ENDC}")
            if confirm.lower() == 'yes':
                try:
                    response = self.session.post(
                        f"{self.api_url}/admin/clear?confirm=true",
                        timeout=10
                    )
                    if response.status_code == 200:
                        print(f"{Colors.OKGREEN}✓ 数据已清空{Colors.ENDC}\n")
                    else:
                        print(f"{Colors.FAIL}清空失败{Colors.ENDC}\n")
                except Exception as e:
                    print(f"{Colors.FAIL}错误: {e}{Colors.ENDC}\n")
            else:
                print(f"{Colors.WARNING}已取消{Colors.ENDC}\n")
        
        elif command == '/nomem':
            print(f"{Colors.WARNING}[下一条消息将不使用记忆系统]{Colors.ENDC}\n")
        
        elif command == '/quit':
            print(f"{Colors.WARNING}晚安~{Colors.ENDC}")
            sys.exit(0)
        
        else:
            print(f"{Colors.FAIL}未知命令: {command}{Colors.ENDC}")
            print(f"输入 {Colors.OKBLUE}/help{Colors.ENDC} 查看帮助\n")


if __name__ == "__main__":
    client = ChatClient()
    
    # 检查连接
    if client.check_connection():
        print()
        client.run()
    else:
        sys.exit(1)
