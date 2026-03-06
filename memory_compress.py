#!/usr/bin/env python3
"""
智能记忆提取和压缩
从 3000+ 条对话中提取关键记忆，减少 AI 加载的数据量
"""

import sqlite3
from pathlib import Path
import json

class MemoryCompressor:
    """智能记忆压缩器"""
    
    def __init__(self, db_path='data/girlfriend.db'):
        self.db_path = Path(db_path)
        self.db = sqlite3.connect(str(self.db_path))
        self.cursor = self.db.cursor()
    
    def analyze_conversations(self):
        """分析对话数据"""
        # 获取统计信息
        self.cursor.execute('SELECT COUNT(*) FROM conversation_pairs')
        total = self.fetchone()[0]
        
        # 分析关键词频率
        keywords = {}
        self.cursor.execute('SELECT user_message, ai_response FROM conversation_pairs')
        
        for user_msg, ai_resp in self.cursor.fetchall():
            # 简单的关键词提取（按长度排序）
            words = set()
            for msg in [user_msg, ai_resp]:
                if msg:
                    # 保留长度 > 2 的词
                    msg_words = [w for w in msg.split() if len(w) > 2]
                    words.update(msg_words)
            
            for word in words:
                keywords[word] = keywords.get(word, 0) + 1
        
        # 返回最频繁的关键词
        top_keywords = sorted(keywords.items(), key=lambda x: x[1], reverse=True)[:20]
        
        return {
            'total_conversations': total,
            'top_keywords': top_keywords,
            'unique_keywords': len(keywords)
        }
    
    def extract_important_memories(self, limit=100):
        """提取最重要的记忆（高质量评分或最新）"""
        queries = [
            # 质量最高的对话
            ('SELECT user_message, ai_response, quality_score FROM conversation_pairs '
             'WHERE quality_score >= 0.8 ORDER BY quality_score DESC, timestamp DESC LIMIT ?', limit),
            
            # 最近的对话
            ('SELECT user_message, ai_response, quality_score FROM conversation_pairs '
             'ORDER BY timestamp DESC LIMIT ?', limit),
        ]
        
        important = {}
        for query, limit_val in queries:
            self.cursor.execute(query, (limit_val,))
            for user_msg, ai_resp, score in self.cursor.fetchall():
                key = (user_msg[:50], ai_resp[:50])  # 用消息的前 50 字符作为 key
                if key not in important:
                    important[key] = {
                        'user': user_msg,
                        'ai': ai_resp,
                        'score': score
                    }
        
        return list(important.values())
    
    def get_memory_summary(self):
        """生成记忆摘要"""
        print("\n" + "=" * 60)
        print("  💭 大脑记忆分析")
        print("=" * 60)
        
        # 总统计
        self.cursor.execute('SELECT COUNT(*) FROM conversation_pairs')
        total = self.fetchone()[0]
        
        self.cursor.execute('SELECT AVG(quality_score) FROM conversation_pairs')
        avg_quality = self.fetchone()[0] or 0
        
        print(f"\n📊 数据统计：")
        print(f"   总对话数: {total} 条")
        print(f"   平均质量: {avg_quality:.2f}")
        
        # 取样分析
        self.cursor.execute('''
            SELECT 
                MIN(timestamp) as first,
                MAX(timestamp) as last,
                COUNT(DISTINCT DATE(timestamp)) as days
            FROM conversation_pairs
        ''')
        
        first, last, days = self.fetchone()
        print(f"   时间跨度: {first} ~ {last}")
        print(f"   活跃天数: {days} 天")
        
        # 高质量对话
        self.cursor.execute('SELECT COUNT(*) FROM conversation_pairs WHERE quality_score >= 0.8')
        high_quality = self.fetchone()[0]
        
        print(f"\n⭐ 记忆质量：")
        print(f"   高质量 (≥0.8): {high_quality} 条 ({high_quality/total*100:.1f}%)")
        print(f"   中等质量 (0.5-0.8): {total - high_quality} 条")
        
        # 建议
        print(f"\n💡 优化建议：")
        if total > 5000:
            print(f"   对话数量较多 ({total} 条)，建议清理低质量数据")
            print(f"   运行: python memory_compress.py --cleanup")
        elif total > 2000:
            print(f"   数据量适中，可进行增量优化")
        else:
            print(f"   数据量充足，保持现有数据即可")
        
        print("\n" + "=" * 60 + "\n")
    
    def cleanup_low_quality(self, threshold=0.3):
        """清理低质量对话"""
        print(f"\n⏳ 清理质量 < {threshold} 的对话...")
        
        self.cursor.execute('SELECT COUNT(*) FROM conversation_pairs WHERE quality_score < ?', (threshold,))
        count = self.fetchone()[0]
        
        if count > 0:
            self.cursor.execute('DELETE FROM conversation_pairs WHERE quality_score < ?', (threshold,))
            self.db.commit()
            print(f"✓ 已删除 {count} 条低质量对话")
        else:
            print(f"✓ 没有需要删除的低质量对话")
    
    def fetchone(self):
        """Shortcut"""
        return self.cursor.fetchone()

if __name__ == '__main__':
    import sys
    
    compressor = MemoryCompressor()
    
    # 显示摘要
    compressor.get_memory_summary()
    
    # 显示分析
    print("\n📈 关键词分析：")
    analysis = compressor.analyze_conversations()
    print(f"   总对话数: {analysis['total_conversations']}")
    print(f"   独特关键词: {analysis['unique_keywords']}")
    print(f"   最常见的 20 个关键词:")
    for word, count in analysis['top_keywords'][:10]:
        print(f"     - {word}: {count} 次")
    
    # 如果指定了 --cleanup 参数
    if '--cleanup' in sys.argv:
        compressor.cleanup_low_quality(threshold=0.3)
