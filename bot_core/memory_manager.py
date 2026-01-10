import sqlite3
import os
from datetime import datetime

DB_PATH = "data/memories.db"

def init_db():
    os.makedirs("data", exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        # 記憶表格
        conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            content TEXT NOT NULL,
            importance INTEGER DEFAULT 1,
            created_at TEXT NOT NULL
        )
        """)
        # 使用者設定表格：儲存目前角色
        conn.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER PRIMARY KEY,
            current_role TEXT DEFAULT 'lover'
        )
        """)

def get_user_role(user_id: int) -> str:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("SELECT current_role FROM user_settings WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        return row[0] if row else 'lover'

def set_user_role(user_id: int, role_name: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
        INSERT INTO user_settings (user_id, current_role)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET current_role = ?
        """, (user_id, role_name, role_name))

# ======================
# 儲存長期記憶（分類版）
# ======================
def save_memory(user_id: int, category: str, content: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
        INSERT INTO memories (user_id, category, content, created_at)
        VALUES (?, ?, ?, ?)
        """, (
            user_id,
            category,
            content,
            datetime.now().isoformat()
        ))

        print(f"🧠 記憶已儲存 | {category} | {content}")

# ======================
# 取出記憶（給 LLM 用）
# ======================
def get_memories(user_id: int, limit: int = 5) -> str:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("""
        SELECT category, content
        FROM memories
        WHERE user_id = ?
        ORDER BY importance DESC, created_at DESC
        LIMIT ?
        """, (user_id, limit)).fetchall()

    if not rows:
        return ""

    return "\n".join([
        f"- ({category}) {content}"
        for category, content in rows
    ])
