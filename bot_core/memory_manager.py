import sqlite3
import os
from datetime import datetime, timedelta, date

DB_PATH = "data/memories.db"

# ======================
# 初始化資料庫
# ======================
def init_db():
    os.makedirs("data", exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:

        # ======================
        # 記憶表
        # ======================
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
        # 使用者設定表
        # ======================
        conn.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER PRIMARY KEY,
            current_role TEXT DEFAULT 'lover',
            bot_name TEXT DEFAULT '你的伴侶',
            user_gender TEXT DEFAULT '未設定',
            timezone TEXT DEFAULT 'Asia/Taipei'
        )
        """)

        # ======================
        # 排程提醒表（UTC）
        # ======================
        conn.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            remind_at TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)

        # ======================
        # 🎂 紀念日 / 生日表
        # ======================
        conn.execute("""
        CREATE TABLE IF NOT EXISTS anniversaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,          -- birthday / anniversary
            month INTEGER NOT NULL,
            day INTEGER NOT NULL,
            label TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)

# ======================
# 使用者角色
# ======================
def get_user_role(user_id: int) -> str:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT current_role FROM user_settings WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        return row[0] if row else "lover"


def set_user_role(user_id: int, role_name: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
        INSERT INTO user_settings (user_id, current_role)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET current_role = excluded.current_role
        """, (user_id, role_name))

# ======================
# 使用者性別
# ======================
def get_user_gender(user_id: int) -> str:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT user_gender FROM user_settings WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        return row[0] if row else "未設定"


def set_user_gender(user_id: int, gender: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
        INSERT INTO user_settings (user_id, user_gender)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET user_gender = excluded.user_gender
        """, (user_id, gender))

# ======================
# 使用者時區
# ======================
def get_user_timezone(user_id: int) -> str:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT timezone FROM user_settings WHERE user_id = ?",
            (user_id,)
        ).fetchone()
    return row[0] if row and row[0] else "Asia/Taipei"


def set_user_timezone(user_id: int, timezone: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
        INSERT INTO user_settings (user_id, timezone)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET timezone = excluded.timezone
        """, (user_id, timezone))

# ======================
# 長期記憶
# ======================
def save_memory(user_id: int, category: str, content: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
        INSERT INTO memories (user_id, category, content, created_at)
        VALUES (?, ?, ?, ?)
        """, (user_id, category, content, datetime.utcnow().isoformat()))

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

    return "\n".join(f"- ({c}) {t}" for c, t in rows)

# ======================
# ⏰ 排程提醒（UTC）
# ======================
def save_reminder(user_id: int, remind_at: str, content: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
        INSERT INTO reminders (user_id, remind_at, content, created_at)
        VALUES (?, ?, ?, ?)
        """, (user_id, remind_at, content, datetime.utcnow().isoformat()))

def get_reminders(user_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute("""
        SELECT remind_at, content
        FROM reminders
        WHERE user_id = ?
        ORDER BY remind_at
        """, (user_id,)).fetchall()

def pop_due_reminders(now_iso: str):
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("""
        SELECT id, user_id, remind_at, content
        FROM reminders
        WHERE remind_at <= ?
        """, (now_iso,)).fetchall()
        for r in rows:
            conn.execute("DELETE FROM reminders WHERE id = ?", (r[0],))
        return rows

# ======================
# 📆 今日 / 本週行程
# ======================
def get_today_reminders(user_id: int):
    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute("""
        SELECT remind_at, content
        FROM reminders
        WHERE user_id = ?
          AND remind_at >= ?
          AND remind_at < ?
        ORDER BY remind_at
        """, (user_id, today, tomorrow)).fetchall()

def get_week_reminders(user_id: int):
    start = date.today().isoformat()
    end = (date.today() + timedelta(days=7)).isoformat()

    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute("""
        SELECT remind_at, content
        FROM reminders
        WHERE user_id = ?
          AND remind_at >= ?
          AND remind_at < ?
        ORDER BY remind_at
        """, (user_id, start, end)).fetchall()

# ======================
# 🎂 紀念日 / 生日
# ======================
def save_anniversary(user_id, type_, month, day, label):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
        INSERT INTO anniversaries (user_id, type, month, day, label, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, type_, month, day, label, datetime.utcnow().isoformat()))

def get_anniversaries(user_id):
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute("""
        SELECT type, month, day, label
        FROM anniversaries
        WHERE user_id = ?
        """, (user_id,)).fetchall()

def get_all_anniversaries():
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute("""
        SELECT user_id, type, month, day, label
        FROM anniversaries
        """).fetchall()
def get_all_users():
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute("""
        SELECT user_id, timezone FROM user_settings
        """).fetchall()
