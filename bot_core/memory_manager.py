# bot_core/memory_manager.py

import sqlite3

DB_PATH = 'data/memories.db'

def init_db():
    """初始化資料庫和表格"""
    # 程式碼：建立連線、建立 user_memories 表格

def get_memories(user_id: int) -> str:
    """根據使用者ID提取長期記憶，以文本形式返回"""
    # 程式碼：查詢資料庫

def save_memory(user_id: int, new_memory: str):
    """保存或更新使用者的長期記憶"""
    # 程式碼：更新資料庫