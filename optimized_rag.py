#!/usr/bin/env python3
"""
优化的 RAG 上下文管理器
避免一次性加载全部数据，使用智能缓存和延迟加载
"""

import sqlite3
from pathlib import Path
from typing import List, Dict, Optional
import hashlib
import time
from functools import lru_cache

class OptimizedRAGManager:
    """优化的 RAG 记忆管理器"""
    
    def __init__(self, db_path='data/girlfriend.db', cache_size=100):
        self.db_path = Path(db_path)
        self.cache_size = cache_size
        self.cache = {}  # 简单的 LRU 缓存
        self.cache_times = {}
        self.last_query = None
        self.query_cache = {}  # 查询结果缓存
        
    def get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    def get_relevant_context(self, query: str, max_results: int = 10, use_cache: bool = True) -> str:
        """
        获取与查询相关的上下文
        优化：只返回最相关的 N 条对话
        """
        # 检查缓存
        cache_key = f"{query}:{max_results}"
        if use_cache and cache_key in self.query_cache:
            cached_time = time.time() - self.cache_times.get(cache_key, 0)
            if cached_time < 300:  # 缓存 5 分钟
                return self.query_cache[cache_key]
        
        # 从数据库获取相关对话
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 简单的全文搜索
        search_query = f"%{query}%"
        cursor.execute('''
            SELECT user_message, ai_response, quality_score
            FROM conversation_pairs
            WHERE user_message LIKE ? OR ai_response LIKE ?
            ORDER BY quality_score DESC, timestamp DESC
            LIMIT ?
        ''', (search_query, search_query, max_results))
        
        results = cursor.fetchall()
        conn.close()
        
        # 构建上下文
        context = self._format_context(results)
        
        # 缓存结果
        self.query_cache[cache_key] = context
        self.cache_times[cache_key] = time.time()
        
        return context
    
    def get_recent_conversations(self, limit: int = 20) -> str:
        """获取最近的对话记录"""
        cache_key = f"recent:{limit}"
        if cache_key in self.query_cache:
            cached_time = time.time() - self.cache_times.get(cache_key, 0)
            if cached_time < 60:  # 缓存 1 分钟
                return self.query_cache[cache_key]
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_message, ai_response
            FROM conversation_pairs
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,))
        
        results = cursor.fetchall()
        conn.close()
        
        context = self._format_context(results, include_quality=False)
        
        self.query_cache[cache_key] = context
        self.cache_times[cache_key] = time.time()
        
        return context
    
    def get_high_quality_memories(self, limit: int = 50, quality_threshold: float = 0.7) -> str:
        """只加载高质量的记忆"""
        cache_key = f"quality:{quality_threshold}:{limit}"
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_message, ai_response, quality_score
            FROM conversation_pairs
            WHERE quality_score >= ?
            ORDER BY quality_score DESC, timestamp DESC
            LIMIT ?
        ''', (quality_threshold, limit))
        
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            return "（暂无高质量记忆）"
        
        context = self._format_context(results)
        return context
    
    def get_context_by_semantics(self, query: str, max_results: int = 5) -> str:
        """
        基于语义相似度获取上下文（简化版）
        实际使用中应使用向量数据库或 embedding 模型
        """
        # 简单实现：按关键词匹配和质量排序
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 提取查询中的关键词
        keywords = self._extract_keywords(query)
        
        if not keywords:
            # 如果没有关键词，返回最近的对话
            return self.get_recent_conversations(max_results)
        
        # 搜索包含这些关键词的对话
        conditions = ' OR '.join([f"(user_message LIKE ? OR ai_response LIKE ?)" for _ in keywords])
        params = []
        for kw in keywords:
            params.extend([f"%{kw}%", f"%{kw}%"])
        params.append(max_results)
        
        cursor.execute(f'''
            SELECT user_message, ai_response, quality_score
            FROM conversation_pairs
            WHERE {conditions}
            ORDER BY quality_score DESC
            LIMIT ?
        ''', params)
        
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            # 如果没有找到相关对话，返回最近的
            return self.get_recent_conversations(max_results)
        
        return self._format_context(results)
    
    def _extract_keywords(self, text: str, min_length: int = 2) -> List[str]:
        """提取关键词"""
        # 简单实现：按空格分割，过滤短词
        words = text.split()
        return [w for w in words if len(w) > min_length][:3]  # 最多 3 个关键词
    
    def _format_context(self, results, include_quality: bool = True) -> str:
        """格式化上下文"""
        if not results:
            return "（没有相关对话记录）"
        
        context_parts = []
        for row in results:
            user_msg = row[0]
            ai_response = row[1]
            quality = row[2] if include_quality and len(row) > 2 else None
            
            part = f"用户: {user_msg}\nAI: {ai_response}"
            if quality:
                part += f" [质量: {quality:.1f}]"
            context_parts.append(part)
        
        return "\n---\n".join(context_parts)
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM conversation_pairs')
        total = cursor.fetchone()[0]
        
        cursor.execute('SELECT AVG(quality_score) FROM conversation_pairs')
        avg_quality = cursor.fetchone()[0] or 0
        
        cursor.execute('''
            SELECT COUNT(*) FROM conversation_pairs
            WHERE quality_score >= 0.8
        ''')
        high_quality = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_conversations': total,
            'average_quality': round(avg_quality, 2),
            'high_quality_count': high_quality,
            'cache_entries': len(self.query_cache)
        }
    
    def clear_cache(self):
        """清除缓存"""
        self.query_cache.clear()
        self.cache_times.clear()

# 全局实例
optimized_rag = OptimizedRAGManager()

if __name__ == '__main__':
    # 测试
    print("🧠 优化的 RAG 管理器测试\n")
    
    # 测试获取最近对话
    print("📝 最近的 5 条对话:")
    recent = optimized_rag.get_recent_conversations(5)
    print(recent[:200] + "...\n")
    
    # 测试获取高质量记忆
    print("⭐ 高质量记忆 (≥0.8):")
    quality = optimized_rag.get_high_quality_memories(5)
    print(quality[:200] + "...\n")
    
    # 测试查询相关对话
    print("🔍 查询'你好'相关的对话:")
    context = optimized_rag.get_relevant_context('你好', max_results=3)
    print(context[:200] + "...\n")
    
    # 统计信息
    print("📊 统计信息:")
    stats = optimized_rag.get_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")
