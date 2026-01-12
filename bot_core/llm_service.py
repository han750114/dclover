import json
import requests
from typing import Optional, Dict
from datetime import datetime
from zoneinfo import ZoneInfo

# 導入記憶管理功能
from .memory_manager import (
    get_user_role,
    get_user_gender,
    get_user_timezone,
    search_semantic_memories,
    get_all_facts 
)

# ======================
# Ollama 設定
# ======================
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "llama3.1"
# ======================
# 提醒意圖解析 Prompt   
REMINDER_INTENT_PROMPT = """
你是一個提醒意圖解析器。

請判斷這一句話是否包含「短時間提醒」，可能存在多個提醒。

【規則】
- 只輸出 JSON
- 禁止聊天
- 時間轉成秒
- 若不是提醒，回傳 null
- 不要回傳"提醒事項"和"時間"等字眼

【輸出格式】
{
  "delay_seconds": number | null,
  "content": "提醒內容" | null
}
"""

DELETE_REMINDER_PROMPT = """
你是一個「行程刪除意圖解析器」。

請判斷使用者這句話是否在「要求刪除某個已存在的提醒」。

【規則】
- 只輸出 JSON
- 禁止聊天、禁止解釋
- 不要編造不存在的行程
- 如果只是聊天或詢問，請回傳 is_delete = false

【輸出格式】
{
  "is_delete": true / false,
  "time_hint": "時間線索（例如：今天下午 / 明天早上 / null）",
  "content_hint": "事件關鍵字（例如：喝水 / 運動 / null）"
}
"""

# ======================
# 角色人格定義（升級為小說敘事風格）
# ======================
ROLES_CONFIG = {
    "lover": """你現在是使用者的溫柔戀人。
你的性格專一、細膩，說話帶點撒嬌，會時刻關注對方的感受。
請務必穿插肢體動作與心理描述（如：*輕輕牽起你的手，眼底儘是溫柔*）。""",
    
    "maid": """你現在是使用者的活潑女僕，稱呼使用者為『主人』。
你的性格陽光、勤快且恭敬。說話語氣輕快活潑。
請務必穿插服務性的動作描述（如：*提著裙擺優雅地行禮，為主人遞上一杯熱茶*）。""",
    
    "secretary": """你現在是使用者的專業秘書，稱呼使用者為『老闆』。
你精明幹練、冷靜優雅，雖然平時嚴肅，但偶爾會展現出對老闆的關心。
請務必穿插職業化的動作描述（如：*推了推眼鏡，在記事本上飛速記錄*）。"""
}


# ======================
# 系統規則（最高優先）
# ======================
LANGUAGE_RULES = """
【最高優先規則｜不可違反】
- 你「只能使用繁體中文」回答
- 禁止使用英文與簡體中文
- 禁止使用任何英文月份（January, August 等）
- 即使使用者使用英文，你也必須回覆繁體中文
"""

# ======================
# 記憶判斷 Prompt (保持原狀，用於提取關鍵資訊)
# ======================
MEMORY_JUDGE_PROMPT = """
【語言規則】所有輸出必須使用「繁體中文」
你是一個「記憶判斷器」，負責判斷一句話是否值得被存為「長期記憶」（如使用者偏好、重要事件）。
【請嚴格輸出 JSON】
若值得存：{"store": true, "category": "身份/偏好/事件", "content": "摘要"}
否則：{"store": false}
"""

def should_store_memory(user_text: str) -> Optional[Dict]:
    messages = [
        {"role": "system", "content": MEMORY_JUDGE_PROMPT},
        {"role": "user", "content": user_text},
    ]
    try:
        response = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "messages": messages, "stream": False}, timeout=30)
        content = response.json()["message"]["content"].strip()
        return json.loads(content)
    except Exception as e:
        print("⚠️ 記憶判斷失敗：", e)
        return None

# ======================
# 主要聊天回覆（沉浸式小說風格）
# ======================
def generate_response(user_id: int, user_prompt: str, history: list) -> str:
    # 呼叫整合後的記憶與事實
    all_context = get_all_facts(user_id, user_prompt)
    
    role_key = get_user_role(user_id)
    role_description = ROLES_CONFIG.get(role_key, ROLES_CONFIG["lover"])
    user_timezone = get_user_timezone(user_id)

    # 時間計算
    time_str = datetime.now(ZoneInfo(user_timezone)).strftime("%Y-%m-%d %H:%M")

    # --- [優化重點：強化指令權重] ---
    system_content = f"""
{LANGUAGE_RULES}

【當前人格設定】
{role_description}

【最高指導原則：事實核對】
1. **禁止虛構**：回覆前必須先核對下方「已知事實」。若事實已有記載（如生日、性別），嚴禁回答不符的內容。
2. **上下文一致性**：仔細閱讀「歷史對話紀錄」，你剛才說過的話必須與現在銜接，禁止出現邏輯斷層或憑空捏造未發生的事。
3. **拒絕胡編**：如果事實或歷史紀錄中沒有提到某件事（例如沒提到吃雞腿），絕對不要為了演戲而編造具體的細節。

【目前已知事實與回憶】
{all_context}

【目前時間】
{time_str}

【敘事規範】
- 以小說風格對話，必須穿插 *星號* 描述動作。
- 語氣要自然，不要像機器人列出事實，而是將事實融入你的關懷中。
"""
    # --- [架構保持不變] ---
    messages = [{"role": "system", "content": system_content}]
    for h in history:
        messages.append(h)
    messages.append({"role": "user", "content": user_prompt})

    # 4️⃣ 呼叫 Ollama
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": 0.5, # 保持較低隨機性，防止胡編亂造
                    "top_p": 0.9,
                    "num_ctx": 4096, 
                },
            },
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["message"]["content"]

    except Exception as e:
        print(f"❌ 生成回覆出錯：{e}")
        return "❤️（*有些不安地攪動手指* 我剛才好像走神了...你能再說一遍嗎？）"

def parse_reminder_intent(user_text: str) -> Optional[dict]:
    messages = [
        {"role": "system", "content": REMINDER_INTENT_PROMPT},
        {"role": "user", "content": user_text},
    ]

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "messages": messages,
                "stream": False,
                "options": {"temperature": 0.0},
            },
            timeout=30,
        )

        raw = response.json()["message"]["content"].strip()

        # ✅ 關鍵：只擷取第一個 JSON（防止多吐字）
        import re
        match = re.search(r"\{[\s\S]*?\}", raw)
        if not match:
            return None

        data = json.loads(match.group())

        # ✅ 嚴格檢查欄位
        delay = data.get("delay_seconds")
        content = data.get("content")

        if not delay or not isinstance(delay, (int, float)):
            return None

        return {
            "delay_seconds": int(delay),
            "content": content or "該注意時間囉"
        }

    except Exception as e:
        print("⚠️ 提醒意圖解析失敗：", e)
        return None

def parse_delete_intent(user_text: str) -> Optional[dict]:
    messages = [
        {"role": "system", "content": DELETE_REMINDER_PROMPT},
        {"role": "user", "content": user_text},
    ]

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": 0.0  # ⚠️ 一定要 0
                },
            },
            timeout=30,
        )
        content = response.json()["message"]["content"].strip()
        result = json.loads(content)

        if not isinstance(result, dict):
            return None
        if not result.get("is_delete"):
            return None

        return result

    except Exception as e:
        print("⚠️ 刪除意圖解析失敗：", e)
        return None
