from email.mime import message
import os
import re
import asyncio
import discord
from discord.ext import commands, tasks
from discord import app_commands
from dotenv import load_dotenv
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from bot_core.schedule_renderer import render_schedule
from bot_core.llm_service import generate_response, should_store_memory
from bot_core.memory_manager import (
    get_all_anniversaries_with_tz,
    init_db,
    save_memory,
    set_user_role,
    set_user_gender,
    set_user_timezone,
    get_user_timezone,
    save_reminder,
    get_reminders,
    pop_due_reminders,
    get_user_role,
    save_anniversary,
    get_anniversaries,
    get_today_reminders,
    get_week_reminders,
    get_all_anniversaries,
)

# ======================
# 環境設定
# ======================
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
print("TOKEN 是否存在：", bool(TOKEN))
user_history = {} # 格式: {user_id: [message1, message2, ...]}

# ======================
# Discord 設定
# ======================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="%", intents=intents)

# ======================
# 啟動事件
# ======================
@bot.event
async def on_ready():
    init_db()

    if not reminder_watcher.is_running():
        reminder_watcher.start()

    if not anniversary_watcher.is_running():
        anniversary_watcher.start()

    if not morning_summary_watcher.is_running():
        morning_summary_watcher.start()
    try:
        synced = await bot.tree.sync()
        print(f"已同步 {len(synced)} 個斜線指令")
    except Exception as e:
        print("Slash sync failed:", e)
    print(f"戀人機器人已上線：{bot.user}")

# ======================
# 排程監看器（唯一真正提醒來源）
# ======================
@tasks.loop(minutes=10)
async def anniversary_watcher():
    now_utc = datetime.utcnow()

    anniversaries = get_all_anniversaries_with_tz() 
    
    # 修正為符合新版本的 UTC 取得方式
    from datetime import UTC 
    now_utc = datetime.now(UTC) 
    
    # 現在這裡有 6 個變數對應 6 個欄位，不會再報錯
    for user_id, type_, month, day, label, tz in anniversaries:
        try:
            user_tz = ZoneInfo(tz)
            local_now = now_utc.astimezone(user_tz)
        except Exception:
            continue

        # 只在當天早上 09:00～09:09 提醒一次
        if local_now.month == month and local_now.day == day:
            if local_now.hour == 9 and local_now.minute < 10:
                try:
                    user = await bot.fetch_user(user_id)
                    if type_ == "birthday":
                        await user.send(f"今天是你的生日！生日快樂！🎉")
                    else:
                        await user.send(f"今天是你的 {label}，別忘了慶祝喔！")
                except Exception as e:
                    print("紀念日提醒失敗:", e)

@tasks.loop(seconds=30)
async def morning_summary_watcher():
    now_utc = datetime.utcnow()

    from bot_core.memory_manager import get_all_users

    users = get_all_users()

    for user_id, tz in users:
        try:
            local_now = now_utc.astimezone(ZoneInfo(tz))
        except Exception:
            continue

        # 只在早上 08:00～08:29 發一次
        if local_now.hour == 8 and local_now.minute < 30:
            reminders = get_today_reminders(user_id)
            if not reminders:
                continue

            role = get_user_role(user_id)

            from bot_core.schedule_renderer import render_schedule_embed
            embed = render_schedule_embed(
                reminders,
                role,
                title="早安！今天的行程提醒"
            )

            try:
                user = await bot.fetch_user(user_id)
                await user.send(embed=embed)
            except Exception as e:
                print("早安提醒失敗:", e)
@tasks.loop(seconds=20)
async def reminder_watcher():
    now_utc = datetime.utcnow().isoformat()
    rows = pop_due_reminders(now_utc)

    for _, user_id, remind_at, content in rows:
        try:
            user = await bot.fetch_user(user_id)
            await user.send(f"提醒你：{content}")
        except Exception as e:
            print("提醒失敗:", e)

# ======================
# 角色切換
# ======================
@bot.tree.command(name="role", description="切換 AI 伴侶的人格設定")
@app_commands.choices(人格=[
    app_commands.Choice(name="溫柔戀人", value="lover"),
    app_commands.Choice(name="活潑女僕", value="maid"),
    app_commands.Choice(name="專業女秘書", value="secretary"),
])
async def role(interaction: discord.Interaction, 人格: app_commands.Choice[str]):
    set_user_role(interaction.user.id, 人格.value)
    await interaction.response.send_message(
        f"✅ 已切換為 **{人格.name}**",
        ephemeral=True
    )

# ======================
# 性別設定
# ======================
@bot.tree.command(name="gender", description="設定您的性別")
@app_commands.choices(性別=[
    app_commands.Choice(name="男性", value="男性"),
    app_commands.Choice(name="女性", value="女性"),
])
async def gender(interaction: discord.Interaction, 性別: app_commands.Choice[str]):
    set_user_gender(interaction.user.id, 性別.value)
    await interaction.response.send_message(
        f"✅ 已記住您的性別：**{性別.name}**",
        ephemeral=True
    )

# ======================
# 時區設定
# ======================
@bot.tree.command(name="timezone", description="設定您的時區（如 Asia/Taipei）")
async def timezone(interaction: discord.Interaction, 時區: str):
    set_user_timezone(interaction.user.id, 時區)
    await interaction.response.send_message(
        f"🕒 已設定時區為 **{時區}**",
        ephemeral=True
    )
# ======================
# Slash：今日行程
# ======================
@bot.tree.command(name="today", description="查看今日行程")
async def today(interaction: discord.Interaction):
    reminders = get_today_reminders(interaction.user.id)
    role = get_user_role(interaction.user.id)

    from bot_core.schedule_renderer import render_schedule_embed
    embed = render_schedule_embed(reminders, role, title="📆 今日行程")

    await interaction.response.send_message(embed=embed, ephemeral=True)


# ======================
# Slash：本週行程
# ======================
@bot.tree.command(name="week", description="查看本週行程")
async def week(interaction: discord.Interaction):
    reminders = get_week_reminders(interaction.user.id)
    role = get_user_role(interaction.user.id)

    from bot_core.schedule_renderer import render_schedule_embed
    embed = render_schedule_embed(reminders, role, title="⏳ 本週行程")

    await interaction.response.send_message(embed=embed, ephemeral=True)

# ======================
# 時間解析（只負責算，不聊天）
# ======================
def parse_datetime(text: str, tz: str):
    try:
        zone = ZoneInfo(tz)
    except ZoneInfoNotFoundError:
        zone = ZoneInfo("Asia/Taipei")

    now = datetime.now(zone)

    m = re.search(
        r"(\d{1,2})/(\d{1,2}).*?(上午|下午|晚上|凌晨)?\s*(\d{1,2})",
        text
    )
    if not m:
        return None

    month, day, period, hour = m.groups()
    month, day, hour = int(month), int(day), int(hour)

    if period in ("下午", "晚上") and hour < 12:
        hour += 12
    if period == "凌晨" and hour == 12:
        hour = 0

    remind_at = datetime(
        year=now.year,
        month=month,
        day=day,
        hour=hour,
        minute=0,
        tzinfo=zone
    )

    if remind_at < now:
        remind_at = remind_at.replace(year=now.year + 1)

    content = re.sub(r"(記得)?提醒我", "", text).strip()
    return remind_at.astimezone(ZoneInfo("UTC")).isoformat(), content

# ======================
# 訊息處理（核心）
# ======================
# @bot.event
# async def on_message(message):
#     if message.author.bot:
#         return

#     await bot.process_commands(message)

#     if not (
#         isinstance(message.channel, discord.DMChannel)
#         or bot.user in message.mentions
#     ):
#         return

#     user_id = message.author.id

#     tz = get_user_timezone(user_id) or "Asia/Taipei"
#     set_user_timezone(user_id, tz)

#     user_text = message.content.replace(
#         f"<@{bot.user.id}>", ""
#     ).strip()

#     # ======================
#     # 🎂 生日 / 紀念日（系統層）
#     # ======================
#     anniv_match = re.search(
#         r"(我的)?(生日|紀念日).*?(\d{1,2})/(\d{1,2})",
#         user_text
#     )

#     if anniv_match:
#         _, kind, month, day = anniv_match.groups()
#         save_anniversary(
#             user_id,
#             "birthday" if kind == "生日" else "anniversary",
#             int(month),
#             int(day),
#             kind
#         )
#         await message.channel.send(
#             f"{message.author.mention} 🎉 我記住了！你的 **{kind} 是 {month} 月 {day} 日**。"
#         )
#         return
    

#     # ======================
#     # 📅 查詢排程（系統事實）
#     # ======================
#     if any(k in user_text for k in ["排程", "行程", "我有什麼行程", "我目前的排程"]):
#         reminders = get_reminders(user_id)
#         role = get_user_role(user_id)
#         reply = render_schedule(reminders, role)
#         await message.channel.send(f"{message.author.mention} {reply}")
#         return
    
#     # ======================
#     # ⏰ 短時間提醒（秒 / 分鐘）【最高優先，禁止進 LLM】
#     # ======================
#     short_matches = re.findall(
#         r"(\d+)\s*(秒|分鐘)\s*後?\s*提醒(?:我)?([^，。\n]*)",
#         user_text
#     )

#     if short_matches:
#         confirmations = []

#         for amount, unit, text in short_matches:
#             amount = int(amount)
#             delay = amount if unit == "秒" else amount * 60
#             text = text.strip() or "該注意時間囉"

#             confirmations.append(f"{amount}{unit}後：{text}")

#             async def short_reminder(d=delay, t=text, uid=user_id):
#                 await asyncio.sleep(d)
#                 try:
#                     user = await bot.fetch_user(uid)
#                     await user.send(f"⏰ 提醒你：{t}")
#                 except Exception as e:
#                     print("短提醒失敗:", e)

#             asyncio.create_task(short_reminder())

#         # ✅ 一次性確認（很重要）
#         confirm_text = "\n".join(
#             f"{i+1}️⃣ {c}" for i, c in enumerate(confirmations)
#         )

#         await message.channel.send(
#             f"{message.author.mention} 我已為你設定 **{len(confirmations)} 個提醒**：\n{confirm_text}"
#         )
#         return  # ⛔ 絕對 return，禁止進 LLM

#     # ======================
#     # ⏰ 新增排程（系統事實）
#     # ======================
#     parsed = parse_datetime(user_text, tz)
#     if parsed:
#         remind_at, content = parsed
#         save_reminder(user_id, remind_at, content)
#         await message.channel.send(
#             f"{message.author.mention} ✅ 已幫你排程提醒：\n"
#             f"🕒 {remind_at[:16]}\n📌 {content}"
#         )
#         return

#     # ======================
#     # 🧠 長期記憶（非排程）
#     # ======================
#     result = should_store_memory(user_text)
#     if result and result.get("store"):
#         save_memory(user_id, result["category"], result["content"])

#     # ======================
#     # 💬 聊天（只聊天，禁止編造行程）
#     # ======================
#     # 1. 初始化該用戶的歷史紀錄快取（若不存在）
#     if user_id not in user_history:
#         user_history[user_id] = []

#     # 2. 調用 generate_response 時傳入「真正的歷史紀錄」
#     reply = generate_response(user_id, user_text, history=user_history[user_id])
    
#     # 3. 更新歷史紀錄（存入這一次的問答）
#     user_history[user_id].append({"role": "user", "content": user_text})
#     user_history[user_id].append({"role": "assistant", "content": reply})
    
#     # 4. 保持記憶新鮮度，只留最近 10 則對話
#     if len(user_history[user_id]) > 10:
#         user_history[user_id] = user_history[user_id][-10:]

#     # 5. 發送回覆（現在只會發送這一次）
#     await message.channel.send(f"{message.author.mention} {reply}")

# # ======================
# # 啟動
# # ======================
# bot.run(TOKEN)
@bot.event
async def on_message(message):
    if message.author.bot: return
    await bot.process_commands(message)

    # 判斷是否為私訊或提到 Bot
    if not (isinstance(message.channel, discord.DMChannel) or bot.user in message.mentions):
        return

    user_id = message.author.id
    user_text = message.content.replace(f"<@{bot.user.id}>", "").strip()
    
    # 取得使用者時區
    tz = get_user_timezone(user_id) or "Asia/Taipei"

    # --- [優化] 生日/紀念日處理：存檔但不中斷對話 ---
    anniv_match = re.search(r"(我的)?(生日|紀念日).*?(\d{1,2})/(\d{1,2})", user_text)
    if anniv_match:
        _, kind, month, day = anniv_match.groups()
        save_anniversary(user_id, "birthday" if kind == "生日" else "anniversary", int(month), int(day), kind)
        # 不再在這裡 return，讓 AI 繼續產生有溫度的回覆

    # --- [優化] 排程查詢 ---
    if any(k in user_text for k in ["排程", "行程", "有什麼行程"]):
        reminders = get_reminders(user_id)
        role = get_user_role(user_id)
        reply = render_schedule(reminders, role)
        await message.channel.send(f"{message.author.mention} {reply}")
        return

    # --- [長期記憶儲存判斷] ---
    result = should_store_memory(user_text)
    if result and result.get("store"):
        save_memory(user_id, result["category"], result["content"])

    # --- [核心：統一聊天邏輯] ---
    if user_id not in user_history:
        user_history[user_id] = []

    # 使用新的整合函式獲取事實與記憶
    # 注意：我們把當前的 user_text 傳進去，讓 RAG 尋找相關回憶
    reply = generate_response(user_id, user_text, history=user_history[user_id])
    
    # 更新短期記憶
    user_history[user_id].append({"role": "user", "content": user_text})
    user_history[user_id].append({"role": "assistant", "content": reply})
    
    if len(user_history[user_id]) > 10:
        user_history[user_id] = user_history[user_id][-10:]

    await message.channel.send(f"{message.author.mention} {reply}")

bot.run(TOKEN)