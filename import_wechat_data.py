#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
直接导入微信数据文件到数据库
支持你的微信数据 JSON 格式
"""

import json
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from database import db
from memory_manager import memory_manager

def import_wechat_json(file_path: str):
    """导入微信 JSON 数据"""
    
    print("\n" + "=" * 70)
    print("  📱 导入微信聊天数据")
    print("=" * 70)
    
    try:
        # 读取文件
        file_path = Path(file_path)
        if not file_path.exists():
            print(f"❌ 文件不存在: {file_path}")
            return False
        
        print(f"\n📂 读取文件: {file_path.name}")
        file_size = file_path.stat().st_size / (1024 * 1024)
        print(f"   大小: {file_size:.1f} MB")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 处理格式
        messages = []
        
        # 格式 1: 直接数组
        if isinstance(data, list):
            messages = data
        # 格式 2: {"success": true, "data": [...]}
        elif isinstance(data, dict) and 'data' in data:
            messages = data['data']
        else:
            print("❌ JSON 格式不支持")
            return False
        
        if not messages:
            print("❌ 没有消息数据")
            return False
        
        print(f"\n📊 消息统计: {len(messages)} 条")
        
        # 分析消息类型
        user_messages = [m for m in messages if m.get('isSelf', False)]
        ai_messages = [m for m in messages if not m.get('isSelf', False) and m.get('type') != 10000]
        
        print(f"   - 用户消息: {len(user_messages)} 条")
        print(f"   - 他人消息: {len(ai_messages)} 条")
        print(f"   - 系统消息: {len([m for m in messages if m.get('type') == 10000])} 条")
        
        # 导入对话对
        print(f"\n⏳ 导入中...\n")
        
        imported = 0
        skipped = 0
        
        # 简单配对策略：用户消息后面跟随的非系统消息为回复
        for i, msg in enumerate(messages):
            if msg.get('isSelf') and msg.get('type') != 10000:  # 用户消息
                content = msg.get('content', '').strip()
                
                # 跳过短消息和多媒体
                if not content or len(content) < 2:
                    skipped += 1
                    continue
                
                # 查找紧跟着的 AI 回复
                for j in range(i + 1, min(i + 5, len(messages))):
                    reply = messages[j]
                    if reply.get('type') != 10000 and not reply.get('isSelf'):  # 非系统消息，非用户
                        reply_content = reply.get('content', '').strip()
                        if reply_content and len(reply_content) >= 2:
                            db.add_conversation_pair(
                                user_message=content,
                                ai_response=reply_content,
                                quality_score=0.7
                            )
                            imported += 1
                            print(f"  [{imported}] ✓ 用户: {content[:30]}...")
                            print(f"        ✓ 回复: {reply_content[:30]}...")
                            break
                
                if imported % 10 == 0 and imported > 0:
                    print(f"  ... 已导入 {imported} 条对话")
        
        print(f"\n✅ 导入完成!")
        print(f"   成功: {imported} 条")
        print(f"   跳过: {skipped} 条")
        
        # 数据库统计
        total = db.get_conversation_count()
        print(f"   数据库总记录: {total} 条")
        
        # 触发记忆提取
        if imported > 0:
            print(f"\n🧠 正在提取关键记忆...")
            memory_manager.extract_and_store_memories()
            print(f"✓ 记忆提取完成")
        
        return True
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON 格式错误: {e}")
        return False
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("\n使用方法:")
        print(f"  python {sys.argv[0]} <JSON文件路径>")
        print(f"\n例子:")
        print(f"  python {sys.argv[0]} messages_wxid_xxxxx.json")
        sys.exit(1)
    
    file_path = sys.argv[1]
    success = import_wechat_json(file_path)
    
    print("\n" + "=" * 70)
    if success:
        print("✅ 导入成功！现在可以与 AI 女友聊天了～")
    else:
        print("❌ 导入失败，请检查上面的错误信息")
    print("=" * 70 + "\n")
    
    sys.exit(0 if success else 1)
