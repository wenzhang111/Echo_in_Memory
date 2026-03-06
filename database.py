"""
数据库操作层 - 聊天记录存储和检索
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import logging

from config import DB_PATH, DB_CONN_TIMEOUT

logger = logging.getLogger(__name__)


class ConversationDatabase:
    """管理聊天记录的数据库操作"""
    
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(str(self.db_path), timeout=DB_CONN_TIMEOUT)
        conn.row_factory = sqlite3.Row  # 返回行对象而不是元组
        return conn
    
    def init_database(self):
        """初始化数据库表"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 1. 完整聊天记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                sender TEXT NOT NULL,  -- 'user' or 'ai'
                content TEXT NOT NULL,  -- 消息内容
                importance_score REAL DEFAULT 0.5,  -- 重要性评分 0-1
                tags TEXT,  -- JSON格式的标签数组
                embedding BLOB  -- 向量嵌入（二进制存储）
            )
        ''')
        
        # 为加速查询创建索引
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_sender ON conversations(sender)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_timestamp ON conversations(timestamp)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_importance ON conversations(importance_score DESC)
        ''')
        
        # 2. 对话对表（用户输入+AI回复打包存储）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversation_pairs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                user_message TEXT NOT NULL,
                ai_response TEXT NOT NULL,
                user_sentiment TEXT,  -- positive, negative, neutral
                context_tags TEXT,  -- JSON格式，记录对话背景
                quality_score REAL DEFAULT 0.5,  -- 对话质量评分
                embedding_user BLOB,  -- 用户消息向量
                embedding_ai BLOB,  -- AI回复向量
                character_id TEXT DEFAULT 'default'  -- 所属角色ID
            )
        ''')
        
        # 尝试添加 character_id 列（已有旧表的情况）
        try:
            cursor.execute("ALTER TABLE conversation_pairs ADD COLUMN character_id TEXT DEFAULT 'default'")
            logger.info("已为 conversation_pairs 添加 character_id 列")
        except sqlite3.OperationalError:
            pass  # 列已存在
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_character_id ON conversation_pairs(character_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_pairs_timestamp ON conversation_pairs(timestamp DESC)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_pairs_char_ts ON conversation_pairs(character_id, timestamp DESC)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_pairs_quality ON conversation_pairs(quality_score DESC)
        ''')
        
        # 3. 长期记忆表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS long_term_memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                category TEXT,  -- 'personality', 'relationship', 'experience', 'preference'
                key TEXT NOT NULL,  -- 记忆的主题关键词
                content TEXT NOT NULL,  -- 记忆内容
                importance_score REAL DEFAULT 0.8,  -- 重要性
                reference_count INTEGER DEFAULT 0,  -- 被引用次数
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_memory_category ON long_term_memories(category)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_memory_key ON long_term_memories(key)
        ''')
        
        # 4. 性格特征表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS personality_traits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trait_name TEXT UNIQUE NOT NULL,  -- 例如：'常用词', '笑声'
                trait_value TEXT NOT NULL,  -- JSON格式的特征值
                frequency REAL DEFAULT 0,  -- 出现频率
                confidence REAL DEFAULT 0.5,  -- 可信度
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("数据库初始化完成")
    
    # ==================== 聊天记录操作 ====================
    def add_conversation(
        self,
        sender: str,
        content: str,
        importance_score: float = 0.5,
        tags: Optional[List[str]] = None,
        embedding: Optional[bytes] = None
    ) -> int:
        """添加单条消息"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        tags_json = json.dumps(tags) if tags else None
        
        cursor.execute('''
            INSERT INTO conversations (sender, content, importance_score, tags, embedding)
            VALUES (?, ?, ?, ?, ?)
        ''', (sender, content, importance_score, tags_json, embedding))
        
        conn.commit()
        msg_id = cursor.lastrowid
        conn.close()
        
        return msg_id
    
    def add_conversation_pair(
        self,
        user_message: str,
        ai_response: str,
        user_sentiment: Optional[str] = None,
        context_tags: Optional[List[str]] = None,
        quality_score: float = 0.5,
        embedding_user: Optional[bytes] = None,
        embedding_ai: Optional[bytes] = None,
        character_id: str = "default"
    ) -> int:
        """添加完整的对话对（用户+AI响应）"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        context_json = json.dumps(context_tags) if context_tags else None
        
        cursor.execute('''
            INSERT INTO conversation_pairs 
            (user_message, ai_response, user_sentiment, context_tags, quality_score, embedding_user, embedding_ai, character_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_message, ai_response, user_sentiment, context_json, quality_score, embedding_user, embedding_ai, character_id))
        
        conn.commit()
        pair_id = cursor.lastrowid
        conn.close()
        
        return pair_id
    
    def get_all_conversations(self, order_by: str = "timestamp DESC", limit: int = None) -> List[Dict]:
        """获取所有聊天记录"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = "SELECT * FROM conversations ORDER BY " + order_by
        if limit:
            query += f" LIMIT {limit}"
        
        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_conversation_pairs(self, limit: int = 100, offset: int = 0, character_id: str = None) -> List[Dict]:
        """获取对话对列表，可按角色过滤"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if character_id:
            cursor.execute('''
                SELECT id, timestamp, user_message, ai_response, quality_score, character_id
                FROM conversation_pairs 
                WHERE character_id = ?
                ORDER BY timestamp DESC 
                LIMIT ? OFFSET ?
            ''', (character_id, limit, offset))
        else:
            cursor.execute('''
                SELECT id, timestamp, user_message, ai_response, quality_score, character_id
                FROM conversation_pairs 
                ORDER BY timestamp DESC 
                LIMIT ? OFFSET ?
            ''', (limit, offset))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_recent_conversations(self, num_pairs: int = 10, character_id: str = None) -> List[Tuple[str, str]]:
        """获取最近的对话对列表（用于上下文），可按角色过滤"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if character_id:
            cursor.execute('''
                SELECT user_message, ai_response 
                FROM conversation_pairs 
                WHERE character_id = ?
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (character_id, num_pairs))
        else:
            cursor.execute('''
                SELECT user_message, ai_response 
                FROM conversation_pairs 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (num_pairs,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [(row[0], row[1]) for row in rows]
    
    def get_conversation_count(self, character_id: str = None) -> int:
        """获取总对话数，可按角色过滤"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if character_id:
            cursor.execute("SELECT COUNT(*) FROM conversation_pairs WHERE character_id = ?", (character_id,))
        else:
            cursor.execute("SELECT COUNT(*) FROM conversation_pairs")
        count = cursor.fetchone()[0]
        conn.close()
        
        return count
    
    # ==================== 长期记忆操作 ====================
    def add_long_term_memory(
        self,
        category: str,
        key: str,
        content: str,
        importance_score: float = 0.8
    ) -> int:
        """添加长期记忆"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id FROM long_term_memories
            WHERE category = ? AND key = ?
            LIMIT 1
        ''', (category, key))
        existing = cursor.fetchone()

        if existing:
            cursor.execute('''
                UPDATE long_term_memories
                SET content = ?,
                    importance_score = ?,
                    last_updated = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (content, importance_score, existing['id']))
            memory_id = existing['id']
        else:
            cursor.execute('''
                INSERT INTO long_term_memories
                (category, key, content, importance_score, last_updated)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (category, key, content, importance_score))
            memory_id = cursor.lastrowid

        conn.commit()
        conn.close()
        
        return memory_id
    
    def get_memories_by_category(self, category: str) -> List[Dict]:
        """按分类获取记忆"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, key, content, importance_score, reference_count, last_updated
            FROM long_term_memories 
            WHERE category = ? 
            ORDER BY importance_score DESC, last_updated DESC, reference_count DESC
        ''', (category,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def search_memories(self, keyword: str) -> List[Dict]:
        """搜索记忆"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, category, key, content, importance_score
            FROM long_term_memories 
            WHERE key LIKE ? OR content LIKE ?
            ORDER BY importance_score DESC
        ''', (f"%{keyword}%", f"%{keyword}%"))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]

    def get_memory_by_id(self, memory_id: int) -> Optional[Dict]:
        """按ID获取单条长期记忆"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT id, created_at, category, key, content, importance_score, reference_count, last_updated
            FROM long_term_memories
            WHERE id = ?
            LIMIT 1
            ''',
            (memory_id,),
        )
        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

    def update_long_term_memory(
        self,
        memory_id: int,
        category: Optional[str] = None,
        key: Optional[str] = None,
        content: Optional[str] = None,
        importance_score: Optional[float] = None,
    ) -> bool:
        """更新长期记忆字段（仅更新传入字段）"""
        fields = []
        values = []

        if category is not None:
            fields.append("category = ?")
            values.append(category)
        if key is not None:
            fields.append("key = ?")
            values.append(key)
        if content is not None:
            fields.append("content = ?")
            values.append(content)
        if importance_score is not None:
            fields.append("importance_score = ?")
            values.append(importance_score)

        if not fields:
            return False

        fields.append("last_updated = CURRENT_TIMESTAMP")
        values.append(memory_id)

        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE long_term_memories SET {', '.join(fields)} WHERE id = ?",
            values,
        )
        conn.commit()
        updated = cursor.rowcount > 0
        conn.close()
        return updated

    def delete_long_term_memory(self, memory_id: int) -> bool:
        """按ID删除长期记忆"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM long_term_memories WHERE id = ?", (memory_id,))
        conn.commit()
        deleted = cursor.rowcount > 0
        conn.close()
        return deleted
    
    def increment_memory_reference(self, memory_id: int):
        """增加记忆的引用计数"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE long_term_memories 
            SET reference_count = reference_count + 1 
            WHERE id = ?
        ''', (memory_id,))
        
        conn.commit()
        conn.close()

    def clear_long_term_memories(self, category: str = None):
        """清空长期记忆，可按分类清空"""
        conn = self.get_connection()
        cursor = conn.cursor()

        if category:
            cursor.execute('DELETE FROM long_term_memories WHERE category = ?', (category,))
        else:
            cursor.execute('DELETE FROM long_term_memories')

        conn.commit()
        conn.close()
    
    # ==================== 性格特征操作 ====================
    def update_personality_trait(
        self,
        trait_name: str,
        trait_value,
        frequency: float = 0.5,
        confidence: float = 0.8
    ):
        """更新或创建性格特征"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        trait_value_json = json.dumps(trait_value, ensure_ascii=False)
        
        cursor.execute('''
            INSERT OR REPLACE INTO personality_traits 
            (trait_name, trait_value, frequency, confidence, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (trait_name, trait_value_json, frequency, confidence))
        
        conn.commit()
        conn.close()
    
    def get_all_personality_traits(self) -> Dict[str, Dict]:
        """获取所有性格特征"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM personality_traits ORDER BY confidence DESC")
        rows = cursor.fetchall()
        conn.close()
        
        traits = {}
        for row in rows:
            row_dict = dict(row)
            row_dict['trait_value'] = json.loads(row_dict['trait_value'])
            traits[row['trait_name']] = row_dict
        
        return traits
    
    def clear_all_data(self):
        """清空所有数据（谨慎使用）"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM conversations")
        cursor.execute("DELETE FROM conversation_pairs")
        cursor.execute("DELETE FROM long_term_memories")
        cursor.execute("DELETE FROM personality_traits")
        
        conn.commit()
        conn.close()
        logger.warning("所有数据已清空")

    def clear_conversation_pairs(self, character_id: str = None) -> int:
        """清除导入的聊天记录（conversation_pairs表）
        
        Args:
            character_id: 如果指定，只清除该角色的记录；否则清除全部
        Returns:
            删除的记录数
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        if character_id:
            cursor.execute("SELECT COUNT(*) FROM conversation_pairs WHERE character_id = ?", (character_id,))
            count = cursor.fetchone()[0]
            cursor.execute("DELETE FROM conversation_pairs WHERE character_id = ?", (character_id,))
        else:
            cursor.execute("SELECT COUNT(*) FROM conversation_pairs")
            count = cursor.fetchone()[0]
            cursor.execute("DELETE FROM conversation_pairs")

        conn.commit()
        conn.close()
        logger.warning(f"已清除 {count} 条聊天记录 (character_id={character_id})")
        return count

    def get_conversation_pairs_summary(self, character_id: str = None) -> Dict:
        """获取聊天记录概况（快速统计，不加载内容）"""
        conn = self.get_connection()
        cursor = conn.cursor()

        if character_id:
            cursor.execute("""
                SELECT COUNT(*) as total,
                       MIN(timestamp) as earliest,
                       MAX(timestamp) as latest,
                       AVG(quality_score) as avg_quality
                FROM conversation_pairs WHERE character_id = ?
            """, (character_id,))
        else:
            cursor.execute("""
                SELECT COUNT(*) as total,
                       MIN(timestamp) as earliest,
                       MAX(timestamp) as latest,
                       AVG(quality_score) as avg_quality
                FROM conversation_pairs
            """)

        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else {"total": 0}

    def search_conversation_pairs_text(self, keyword: str, limit: int = 50, character_id: str = None) -> List[Dict]:
        """基于关键词的快速文本搜索（SQL LIKE），比向量检索快得多"""
        conn = self.get_connection()
        cursor = conn.cursor()
        pattern = f"%{keyword}%"

        if character_id:
            cursor.execute('''
                SELECT id, timestamp, user_message, ai_response, quality_score
                FROM conversation_pairs
                WHERE character_id = ? AND (user_message LIKE ? OR ai_response LIKE ?)
                ORDER BY quality_score DESC, timestamp DESC
                LIMIT ?
            ''', (character_id, pattern, pattern, limit))
        else:
            cursor.execute('''
                SELECT id, timestamp, user_message, ai_response, quality_score
                FROM conversation_pairs
                WHERE user_message LIKE ? OR ai_response LIKE ?
                ORDER BY quality_score DESC, timestamp DESC
                LIMIT ?
            ''', (pattern, pattern, limit))

        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]


# 全局数据库实例
db = ConversationDatabase()
