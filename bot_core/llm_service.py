# bot_core/llm_service.py

from openai import OpenAI
# ... 其他必要的導入

client = OpenAI() # 假設 API Key 已在環境變數中設定好

SYSTEM_PROMPT = "你是一個虛擬戀人..." # 角色設定

def generate_response(user_id: int, user_prompt: str, history: list) -> str:
    """生成 LLM 的回覆"""
    
    # 1. 獲取長期記憶
    from .memory_manager import get_memories
    long_term_memory = get_memories(user_id)
    
    # 2. 構建完整的 System Prompt
    full_system_prompt = f"{SYSTEM_PROMPT}\n---\n關於戀人的重要記憶：{long_term_memory}"
    
    # 3. 構建 messages 列表（結合長期、短期記憶和新提問）
    messages = [
        {"role": "system", "content": full_system_prompt},
        # ... 這裡加入短期對話歷史 (history)
        {"role": "user", "content": user_prompt}
    ]
    
    # 4. 呼叫 LLM API
    # ... 呼叫 client.chat.completions.create(...)
    
    return "LLM 的回覆文本"