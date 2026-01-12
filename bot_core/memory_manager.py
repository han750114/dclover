import sqlite3
import os
from datetime import datetime, timedelta, date
import chromadb
from chromadb.utils import embedding_functions

DB_PATH = "data/memories.db"
CHROMA_PATH = "data/vector_db"

ollama_ef = embedding_functions.OllamaEmbeddingFunction(
    url="http://localhost:11434/api/embeddings",
    model_name="bge-m3"
)
chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
collection = chroma_client.get_or_create_collection(
    name="user_memories", 
    embedding_function=ollama_ef
)

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

        conn.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER PRIMARY KEY,
            current_role TEXT DEFAULT 'lover',
            bot_name TEXT DEFAULT '你的伴侶',
            user_gender TEXT DEFAULT '未設定',
            timezone TEXT DEFAULT 'Asia/Taipei'
        )
        """)


        conn.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            remind_at TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)

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

def save_memory(user_id: int, category: str, content: str):
    timestamp = datetime.utcnow().isoformat()
    
    # 1. 存入 SQLite (供系統查詢)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute("""
        INSERT INTO memories (user_id, category, content, created_at)
        VALUES (?, ?, ?, ?)
        """, (user_id, category, content, timestamp))
        memory_id = str(cursor.lastrowid)

    # 2. 存入 ChromaDB (供語義搜尋)
    collection.add(
        documents=[content],
        ids=[f"mem_{memory_id}"],
        metadatas=[{"user_id": user_id, "category": category}]
    )

def search_semantic_memories(user_id: int, query_text: str, limit: int = 3):
    """搜尋與當前話題最相關的 3 條記憶"""
    try:
        results = collection.query(
            query_texts=[query_text],
            n_results=limit,
            where={"user_id": user_id}
        )
        if not results['documents'] or not results['documents'][0]:
            return ""
        return "\n".join([f"- {doc}" for doc in results['documents'][0]])
    except Exception as e:
        print(f"⚠️ 語義搜尋失敗: {e}")
        return ""

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
def get_all_anniversaries_with_tz():
    """
    使用 JOIN 同時抓取紀念日與使用者的時區設定
    """
    with sqlite3.connect(DB_PATH) as conn:
        query = """
        SELECT a.user_id, a.type, a.month, a.day, a.label, 
               COALESCE(s.timezone, 'Asia/Taipei') as tz
        FROM anniversaries a
        LEFT JOIN user_settings s ON a.user_id = s.user_id
        """
        return conn.execute(query).fetchall()
def get_all_users():
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute("""
        SELECT user_id, timezone FROM user_settings
        """).fetchall()
def get_all_facts(user_id: int, query_text: str = None):
    facts = []
    with sqlite3.connect(DB_PATH) as conn:
        reminders = conn.execute(
            "SELECT remind_at, content FROM reminders WHERE user_id = ? AND remind_at >= ? ORDER BY remind_at LIMIT 5",
            (user_id, datetime.utcnow().isoformat())
        ).fetchall()
        for r in reminders:
            facts.append(f"系統已排定行程：{r[0].replace('T', ' ')} - {r[1]}")
        annivs = conn.execute(
            "SELECT label, month, day FROM anniversaries WHERE user_id = ?",
            (user_id,)
        ).fetchall()
        for a in annivs:
            facts.append(f"重要日子 - {a[0]}：{a[1]}月{a[2]}日")
        
        reminders = conn.execute(
            "SELECT remind_at, content FROM reminders WHERE user_id = ? AND remind_at >= ? ORDER BY remind_at LIMIT 5",
            (user_id, datetime.utcnow().isoformat())
        ).fetchall()
        for r in reminders:
            time_str = r[0].replace("T", " ")[:16]
            facts.append(f"已排定行程：{time_str} - {r[1]}")

        settings = conn.execute(
            "SELECT user_gender, timezone FROM user_settings WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        if settings:
            facts.append(f"對方性別：{settings[0]}")
            facts.append(f"對方時區：{settings[1]}")

    semantic_mems = ""
    if query_text:
        try:
            results = collection.query(
                query_texts=[query_text],
                n_results=3,
                where={"user_id": user_id}
            )
            if results['documents'] and results['documents'][0]:
                semantic_mems = "\n".join([f"往事片段：{d}" for d in results['documents'][0]])
        except Exception as e:
            print(f"ChromaDB 查詢失敗: {e}")

    fact_str = "\n".join(facts)
    return f"【已知事實】\n{fact_str}\n\n【相關回憶】\n{semantic_mems}"

def delete_reminder_by_index(user_id: int, index: int) -> bool:
    """
    依照使用者目前行程排序後的「第 index 筆」刪除
    index 從 1 開始
    """
    import sqlite3
    from .memory_manager import DB_PATH 

    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("""
            SELECT id
            FROM reminders
            WHERE user_id = ?
            ORDER BY remind_at
        """, (user_id,)).fetchall()

        if index < 1 or index > len(rows):
            return False

        reminder_id = rows[index - 1][0]
        conn.execute(
            "DELETE FROM reminders WHERE id = ?",
            (reminder_id,)
        )
        return True