#!/usr/bin/env python3
"""分析数据库性能"""

import sqlite3
import time

db = sqlite3.connect('data/girlfriend.db')
cursor = db.cursor()

# 检查表结构
cursor.execute("PRAGMA table_info(conversation_pairs)")
columns = cursor.fetchall()
print('✅ 对话表结构:')
for col in columns:
    print(f'   {col[1]}: {col[2]}')

# 检查数据统计
cursor.execute('SELECT COUNT(*) FROM conversation_pairs')
total = cursor.fetchone()[0]
print(f'\n📊 数据统计:')
print(f'   总对话数: {total}')

# 性能测试
print('\n⏱️ 加载性能:')

start = time.time()
cursor.execute('SELECT user_message, ai_response FROM conversation_pairs LIMIT 50')
data = cursor.fetchall()
elapsed = time.time() - start
print(f'   加载50条耗时: {elapsed*1000:.1f}ms')

start = time.time()
cursor.execute('SELECT user_message, ai_response FROM conversation_pairs LIMIT 100')
data = cursor.fetchall()
elapsed = time.time() - start
print(f'   加载100条耗时: {elapsed*1000:.1f}ms')

start = time.time()
cursor.execute('SELECT user_message, ai_response FROM conversation_pairs LIMIT 500')
data = cursor.fetchall()
elapsed = time.time() - start
print(f'   加载500条耗时: {elapsed*1000:.1f}ms')

start = time.time()
cursor.execute('SELECT user_message, ai_response FROM conversation_pairs')
data = cursor.fetchall()
elapsed = time.time() - start
print(f'   加载全部 ({len(data)} 条) 耗时: {elapsed*1000:.1f}ms')

print('\n💡 优化建议:')
if elapsed > 1:
    print(f'   ⚠️  全量加载超过1秒，建议使用分页加载')
else:
    print(f'   ✓ 全量加载性能不错，可适度优化')
