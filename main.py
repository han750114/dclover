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
    matches = re.findall(
        r"(\d+)\s*(秒|分鐘)\s*後?\s*提醒(?:我)?([^，。\n]+)",
        user_text
    )

    if matches:
        confirmations = []

        for amount, unit, reminder_text in matches:
            amount = int(amount)
            delay = amount if unit == "秒" else amount * 60
            reminder_text = reminder_text.strip()

            if not reminder_text:
                reminder_text = "該注意時間囉"

            confirmations.append(f"{amount}{unit}後：{reminder_text}")

            async def reminder_task(d=delay, text=reminder_text):
                await asyncio.sleep(d)
                await message.channel.send(
                    f"提醒你一下：{text} ⏰"
                )
                reminder_tasks.discard(asyncio.current_task())

            task = asyncio.create_task(reminder_task())
            reminder_tasks.add(task)

        # ✅ 一次性確認所有提醒
        confirmation_text = "\n".join(
            f"{i+1}️⃣ {c}" for i, c in enumerate(confirmations)
        )

        await message.channel.send(
            f"好，我幫你設定了 {len(confirmations)} 個提醒：\n{confirmation_text}"
        )
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
