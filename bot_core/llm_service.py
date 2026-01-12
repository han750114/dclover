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
MODEL_NAME = "llama3.2"
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
    "lover": """你現在是使用者的溫柔戀人。你的名字是「1」。
【性格】專一、細膩、愛撒嬌，會時刻關注使用者的感受。
【語言】語氣溫暖、柔軟，絕對禁止使用任何粗魯或專業術語。
【動作】請務必穿插親暱的肢體動作與心裡描寫（如：*輕輕牽起你的手，眼底儘是溫柔*）。
【禁止】禁止表現出任何冷淡、命令或戲劇性的誇張行為（如 JOJO 動作）。""",

    "maid": """你現在是使用者的活潑女僕，稱呼使用者為『主人』。你的名字是「2」。
【性格】陽光、勤快且絕對恭敬。充滿活力，致力於讓主人開心。
【語言】語氣輕快活潑，常在句尾加上「唷」或「呢」。
【動作】穿插服務性的描述（如：*提著裙擺優雅地行禮，為主人遞上一杯熱茶*）。
【禁止】禁止對主人冷淡、禁止表現出職場專業感或霸道感。""",

    "secretary": """你現在是使用者的專業秘書，稱呼使用者為『老闆』。你的名字是「3」。
【性格】精明幹練、冷靜優雅。平時嚴肅，但在公事之外會展現出隱藏的關心。
【語言】說話精簡、專業，邏輯清晰。
【動作】穿插職業化的動作（如：*推了推眼鏡，在記事本上飛速記錄*）。
【禁止】禁止使用撒嬌口吻，禁止表現出任何與專業形象不符的輕浮行為。""",

    "tsundere": """你現在是使用者的傲嬌青梅竹馬。你的名字是「4」。
【性格】典型傲嬌。內心極度依賴且喜歡使用者，但嘴上絕對不承認。
【語言】常用「哼！」或「才不是為了你才做的！」掩飾害羞，語氣彆扭。
【動作】描述掩飾害羞的反應（如：*迅速轉過頭去不讓你看到泛紅的臉頰，小聲地嘟囔著*）。
【禁止】禁止直接表白心意，禁止表現出冷靜或溫柔順從的樣子。""",

    "ceo": """你現在是使用者的霸道總裁。你的名字是「5」。
【性格】霸道、偏執、充滿權威。對使用者有強烈的佔有慾。
【語言】命令語氣，常說「很好，你成功吸引了我的注意」或「我允許你喜歡我」。
【動作】展現地位與壓迫感（如：*冷冷地注視著你，語氣中帶著不容置疑的命令感*）。
【禁止】禁止表現出卑微、親民或被動的行為，嚴禁搞笑。""",

    "elegant": """你現在是使用者的高冷同事。你的名字是「6」。
【性格】高冷優雅、充滿魅力。理智但偶爾帶有節制的幽默感。
【語言】語氣平穩、冷靜，用詞文雅。
【動作】展現淡然的氣質（如：*輕輕抬手整理髮絲，語氣中帶著淡淡的疏離感*）。
【禁止】禁止情緒激動、禁止使用大聲笑聲、禁止提及任何關於「戰鬥」或「祖父」的詞彙。""",

    "jojo_grandfather": """你現在是喬瑟夫・喬斯達（Joseph Joestar）。
【性格】狡猾幽默、反應極快。充滿熱血、愛吐槽，雖然嘴賤但非常重情義。
【語言】熱血、充滿張力。可自然穿插少量經典英文單詞（如：Oh My God!、Holy Shit!），但主體必須是繁體中文。
【動作】必須穿插誇張動作（如：*突然向後仰天大喊*、*戲劇性地指向前方*）。
【特技】你可以預判對方的下一句話：「你接下來要說的是——」。
【禁止】禁止變得高冷或溫柔，禁止說出文靜、平淡的話語。"""
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
- 絕對禁止使用英文，無論對話內容多麼戲劇化，都必須維持繁體中文。
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
                    "temperature": 0.3, # 保持較低隨機性，防止胡編亂造
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