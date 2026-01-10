import sqlite3
import os
from datetime import datetime

DB_PATH = "data/memories.db"

# ======================
# 初始化資料庫
# ======================
def init_db():
    os.makedirs("data", exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
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
