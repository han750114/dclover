import os
import re
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

from bot_core.llm_service import generate_response, should_store_memory
from bot_core.memory_manager import init_db, save_memory

# ======================
# 環境設定
# ======================
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
print("TOKEN 是否存在：", bool(TOKEN))

# ======================
# Discord 設定
# ======================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="%", intents=intents)

# ======================
# 提醒任務池（避免被覆蓋）
# ======================
reminder_tasks = set()

# ======================
# 啟動事件
# ======================
@bot.event
async def on_ready():
    init_db()
    print(f"❤️ 戀人機器人已上線：{bot.user}")

# ======================
# 訊息處理
# ======================
@bot.event
async def on_message(message):
    # 忽略 bot 自己
    if message.author.bot:
        return

    # 先讓指令系統能用
    await bot.process_commands(message)

    # 只在 私訊 或 被提及 時回應
    if not (
        isinstance(message.channel, discord.DMChannel)
        or bot.user in message.mentions
    ):
        return

    user_id = message.author.id

    # 清掉 mention
    user_text = message.content.replace(
        f"<@{bot.user.id}>", ""
    ).strip()

    # ==================================================
    # ⏰ 通用延遲提醒（最高優先，不進 LLM）
    # ==================================================
    match = re.search(r"(\d+)\s*(秒|分鐘)", user_text)

    if match and "提醒" in user_text:
        amount = int(match.group(1))
        unit = match.group(2)
        delay = amount if unit == "秒" else amount * 60

        # 抽出提醒內容
        reminder_text = user_text
        reminder_text = re.sub(r"\d+\s*(秒|分鐘)", "", reminder_text)
        reminder_text = reminder_text.replace("後", "")
        reminder_text = reminder_text.replace("提醒我", "")
        reminder_text = reminder_text.replace("提醒", "")
        reminder_text = reminder_text.strip()

        if not reminder_text:
            reminder_text = "該注意時間囉"

        # ✅ 立刻確認（避免「沒理我」的感覺）
        await message.channel.send(
            f"好，我收到囉，我會在 {amount}{unit} 後提醒你：{reminder_text} ⏰"
        )

        async def reminder_task():
            await asyncio.sleep(delay)
            await message.channel.send(
                f"提醒你一下：{reminder_text} ⏰"
            )
            reminder_tasks.discard(asyncio.current_task())

        task = asyncio.create_task(reminder_task())
        reminder_tasks.add(task)
        return

    # ==================================================
    # 🧠 LLM 記憶判斷
    # ==================================================
    result = should_store_memory(user_text)

    if result and result.get("store"):
        save_memory(
            user_id=user_id,
            category=result["category"],
            content=result["content"]
        )

    # ==================================================
    # 💬 產生聊天回覆（只負責聊天）
    # ==================================================
    reply = generate_response(
        user_id=user_id,
        user_prompt=user_text,
        history=[]
    )

    await message.channel.send(reply)

# ======================
# 啟動 Bot
# ======================
bot.run(TOKEN)
