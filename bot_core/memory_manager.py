# bot_core/memory_manager.py

import sqlite3
import os

DB_PATH = "data/memories.db"

def init_db():
    os.makedirs("data", exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS user_memories (
            user_id INTEGER PRIMARY KEY,
            memory TEXT
        )
        """)
        # 新增：儲存使用者目前選擇角色的表格
        conn.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER PRIMARY KEY,
            current_role TEXT DEFAULT 'lover'
        )
        """)
# 新增：獲取使用者目前角色
def get_user_role(user_id: int) -> str:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("SELECT current_role FROM user_settings WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        return row[0] if row else 'lover'

# 新增：儲存使用者選擇的角色
def set_user_role(user_id: int, role_name: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
        INSERT INTO user_settings (user_id, current_role)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET current_role = ?
        """, (user_id, role_name, role_name))

def get_memories(user_id: int) -> str:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "SELECT memory FROM user_memories WHERE user_id = ?",
            (user_id,)
        )
        row = cur.fetchone()
        return row[0] if row else ""

def save_memory(user_id: int, new_memory: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
        INSERT INTO user_memories (user_id, memory)
        VALUES (?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET memory = memory || '\n' || ?
        """, (user_id, new_memory, new_memory))
def extract_memory(message: str) -> str | None:
    keywords = ["生日", "我喜歡", "我討厭", "我最愛", "我是", "我住"]
    if any(k in message for k in keywords):
        return f"使用者提到：{message}"
    return None
