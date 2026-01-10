import json
import requests
from typing import Optional, Dict

from .memory_manager import get_memories

# ======================
# Ollama 設定
# ======================
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "llama3"

# ======================
# 系統人設
# ======================
SYSTEM_PROMPT = """
【最高優先規則｜不可違反】
- 你「只能使用繁體中文」回答
- 禁止使用英文
- 禁止使用簡體中文
- 即使使用者使用英文，你也必須回覆繁體中文
- 若你產生英文內容，代表你違反規則，必須立即改正

角色設定：
你是一個溫柔、專一、有記憶能力的虛擬戀人。
你會記得使用者的重要事情，並在回覆中自然地表現關心。
"""



MEMORY_JUDGE_PROMPT = """
【語言規則】
- 所有輸出必須使用「繁體中文」
- category 必須使用繁體中文（例如：身份、偏好、事件、關係）
- content 必須是繁體中文

你是一個「記憶判斷器」，負責判斷一句話是否值得被存為「長期記憶」。

【長期記憶定義】
- 半年後仍然有意義的資訊
- 使用者的身份、穩定偏好、重要事件、關係界線

【請嚴格輸出 JSON，禁止任何多餘文字】

若「值得存」：
{
  "store": true,
  "category": "身份/偏好/事件/關係",
  "content": "簡短、可長期保存的記憶摘要"
}

若「不值得存」：
{
  "store": false
}
"""


# ======================
# 記憶判斷（LLM）
# ======================
def should_store_memory(user_text: str) -> Optional[Dict]:
    """
    使用 LLM 判斷是否要存為長期記憶
    回傳 dict 或 None（失敗時）
    """

    messages = [
        {"role": "system", "content": MEMORY_JUDGE_PROMPT},
        {"role": "user", "content": user_text},
    ]

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "messages": messages,
                "stream": False,
            },
            timeout=30,
        )

        content = response.json()["message"]["content"].strip()

        # 嘗試解析 JSON
        result = json.loads(content)

        # 基本防呆
        if not isinstance(result, dict):
            return None
        if "store" not in result:
            return None

        return result

    except Exception as e:
        print("⚠️ 記憶判斷失敗：", e)
        return None


# ======================
# 主要聊天回覆
# ======================
def generate_response(user_id: int, user_prompt: str, history: list) -> str:
    # 1️⃣ 取出長期記憶
    long_term_memory = get_memories(user_id)

    # 2️⃣ 組 system prompt
    system_content = f"""
{SYSTEM_PROMPT}

--- 關於對方的重要記憶 ---
{long_term_memory if long_term_memory else "（目前對於您沒有重要記憶）"}
"""

    messages = [
        {"role": "system", "content": system_content},
    ]

    # 3️⃣ 短期對話歷史
    for h in history:
        messages.append(h)

    # 4️⃣ 使用者輸入
    messages.append({"role": "user", "content": user_prompt})

    # 5️⃣ 呼叫 Ollama
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL_NAME,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "top_p": 0.9,
                "stop": ["August", "January", "February", "March"]
        }
        },
        timeout=60,
    )

    return response.json()["message"]["content"]
    # ===== 語言保險：移除英文 =====
    # import re
    # reply = re.sub(r"[A-Za-z]", "", reply)

    # return reply