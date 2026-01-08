# # bot_core/llm_service.py

# from openai import OpenAI
# # ... 其他必要的導入

# client = OpenAI() # 假設 API Key 已在環境變數中設定好

# SYSTEM_PROMPT = "你是一個虛擬戀人..." # 角色設定

# def generate_response(user_id: int, user_prompt: str, history: list) -> str:
#     """生成 LLM 的回覆"""
    
#     # 1. 獲取長期記憶
#     from .memory_manager import get_memories
#     long_term_memory = get_memories(user_id)
    
#     # 2. 構建完整的 System Prompt
#     full_system_prompt = f"{SYSTEM_PROMPT}\n---\n關於戀人的重要記憶：{long_term_memory}"
    
#     # 3. 構建 messages 列表（結合長期、短期記憶和新提問）
#     messages = [
#         {"role": "system", "content": full_system_prompt},
#         # ... 這裡加入短期對話歷史 (history)
#         {"role": "user", "content": user_prompt}
#     ]
    
#     # 4. 呼叫 LLM API
#     # ... 呼叫 client.chat.completions.create(...)
    
#     return "LLM 的回覆文本"
import requests
from .memory_manager import get_memories

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "llama3"

SYSTEM_PROMPT = """
使用繁體中文回答。
你是一個溫柔、專一、有記憶能力的虛擬戀人。
你會記得使用者的重要事情，並在回覆中自然地表現關心。
"""

def generate_response(user_id: int, user_prompt: str, history: list) -> str:
    # 1️⃣ 取出長期記憶
    long_term_memory = get_memories(user_id)

    # 2️⃣ 組 system prompt
    system_content = f"""
{SYSTEM_PROMPT}

--- 關於對方的重要記憶 ---
{long_term_memory if long_term_memory else "（目前沒有記憶）"}
"""

    messages = [
        {"role": "system", "content": system_content},
    ]

    # 3️⃣ 加入短期歷史
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
            "stream": False
        }
    )

    return response.json()["message"]["content"]
