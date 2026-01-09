import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

from bot_core.llm_service import generate_response
from bot_core.memory_manager import init_db, save_memory

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="%", intents=intents)

def extract_memory(message: str):
    keywords = ["生日", "我喜歡", "我討厭", "我最愛", "我是", "我住","語言","興趣","工作","職業","夢想","目標"]
    if any(k in message for k in keywords):
        return f"使用者的重要資訊：{message}"
    return None

@bot.event
async def on_ready():
    init_db()
    print(f"❤️ 戀人機器人已上線：{bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # 仍允許指令
    await bot.process_commands(message)

    # 只在私訊 or 提及時回應（避免洗版）
    if isinstance(message.channel, discord.DMChannel) or bot.user in message.mentions:
        user_id = message.author.id
        user_text = message.content.replace(f"<@{bot.user.id}>", "").strip()

        memory = extract_memory(user_text)
        if memory:
            save_memory(user_id, memory)

        reply = generate_response(
            user_id=user_id,
            user_prompt=user_text,
            history=[]
        )

        await message.channel.send(reply)

print("TOKEN 是否存在：", bool(TOKEN))
bot.run(TOKEN)
