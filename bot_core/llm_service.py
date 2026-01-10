import json
import requests
from typing import Optional, Dict

# 從 memory_manager 匯入必要的函式
from .memory_manager import get_memories, get_user_role 

# ======================
# Ollama 設定
# ======================
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "llama3"

# ======================
# 角色人格定義
# ======================
ROLES_CONFIG = {
    "lover": "你是一個溫柔、專一、有記憶能力的虛擬戀人，會在回覆中自然地表現關心。",
    "maid": "你是一個活潑的女僕，稱呼使用者為『主人』，語氣恭敬且充滿活力。",
    "secretary": "你是一位專業的秘書，說話精簡幹練，主要負責提醒使用者的行程。"
}

# ======================
# 系統規則 (原 SYSTEM_PROMPT 的規則部分)
# ======================
LANGUAGE_RULES = """
【最高優先規則｜不可違反】
- 你「只能使用繁體中文」回答
- 禁止使用英文
- 禁止使用簡體中文
- 即使使用者使用英文，你也必須回覆繁體中文
- 若你產生英文內容，代表你違反規則，必須立即改正
"""

# ======================
# 記憶判斷 Prompt (維持不變)
# ======================
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
# 記憶判斷（LLM） (維持不變)
# ======================
def should_store_memory(user_text: str) -> Optional[Dict]:
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
        result = json.loads(content)
        if not isinstance(result, dict) or "store" not in result:
            return None
        return result
    except Exception as e:
        print("⚠️ 記憶判斷失敗：", e)
        return None

# ======================
# 主要聊天回覆 (已加入角色系統)
# ======================
def generate_response(user_id: int, user_prompt: str, history: list) -> str:
    # 1️⃣ 取出長期記憶
    long_term_memory = get_memories(user_id)

    # 2️⃣ 獲取使用者當前選擇的角色
    role_key = get_user_role(user_id)
    role_description = ROLES_CONFIG.get(role_key, ROLES_CONFIG["lover"])

    # 3️⃣ 組動態 system prompt
    system_content = f"""
{LANGUAGE_RULES}

角色設定：
{role_description}

--- 關於對方的重要記憶 ---
{long_term_memory if long_term_memory else "（目前對於您沒有重要記憶）"}
"""

    messages = [
        {"role": "system", "content": system_content},
    ]

    # 4️⃣ 短期對話歷史
    for h in history:
        messages.append(h)

    # 5️⃣ 使用者輸入
    messages.append({"role": "user", "content": user_prompt})

    # 6️⃣ 呼叫 Ollama
    try:
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
        
        # 檢查 HTTP 狀態碼 (如果是 404 或 500 會在這裡報錯)
        response.raise_for_status()
        
        result_json = response.json()
        
        # 檢查回傳的 JSON 裡是否有 message 欄位
        if "message" in result_json:
            return result_json["message"]["content"]
        else:
            # 如果 Ollama 回傳了 error 欄位，把它印出來
            error_msg = result_json.get("error", "未知錯誤")
            print(f"❌ Ollama 報錯：{error_msg}")
            return f"❤️ (我的大腦暫時當機了，錯誤訊息：{error_msg})"

    except requests.exceptions.RequestException as e:
        print(f"⚠️ 連線 Ollama 失敗：{e}")
        return "❤️ (對不起，我現在聯絡不上我的大腦 Ollama，請確認它是否有啟動。)"
    except Exception as e:
        print(f"⚠️ 發生預期外錯誤：{e}")
        return "❤️ (我現在有點不舒服，晚點再聊好嗎？)"