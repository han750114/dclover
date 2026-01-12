# from email.mime import message
import os
import re
import asyncio
import discord
from discord.ext import commands, tasks
from discord import app_commands
from dotenv import load_dotenv
from datetime import timedelta
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from bot_core.llm_service import parse_reminder_intent
from bot_core.llm_service import parse_delete_intent
from bot_core.memory_manager import get_reminders, delete_reminder_by_index


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
short_reminder_tasks = {}  
# 格式：
# { user_id: [ { "content": str, "task": asyncio.Task } ] }

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

def split_into_clauses(text: str):
    return [
        t.strip()
        for t in re.split(r"[，,、]", text)
        if t.strip()
    ]

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



async def short_timer(bot, delay: int, content: str, user_id: int):
    await asyncio.sleep(delay)
    try:
        user = await bot.fetch_user(user_id)
        await user.send(f"（*輕輕拍了拍你的肩膀*）提醒主人：{content}")
    except asyncio.CancelledError:
        # 正常取消，不當錯誤
        pass
    except Exception as e:
        print("短提醒執行失敗:", e)

# ======================
# 時間解析（只負責算，不聊天）
# ======================
def parse_datetime(text: str, tz: str):
    WEEKDAY_MAP = {
    "一": 0,
    "二": 1,
    "三": 2,
    "四": 3,
    "五": 4,
    "六": 5,
    "日": 6,
    "天": 6,
    }

    try:
        zone = ZoneInfo(tz)
    except ZoneInfoNotFoundError:
        zone = ZoneInfo("Asia/Taipei")

    now = datetime.now(zone)

    weekday_match = re.search(r"(禮拜|星期)([一二三四五六日天5])", text)
    # 先抓「6點」這種（最準）
    time_match = re.search(
        r"(下午|晚上|上午|早上)?\s*(\d{1,2})\s*點",
        text
    )

    # 如果沒寫「點」，再退而求其次
    if not time_match:
        time_match = re.search(
            r"(下午|晚上|上午|早上)\s*(\d{1,2})",
            text
        )

    # ❶ 先判斷是否只有日期（沒有時間）
    date_only = re.search(r"(\d{1,2})/(\d{1,2})", text)

    if not time_match and date_only:
        month, day = map(int, date_only.groups())

        remind_at = datetime(
            year=now.year,
            month=month,
            day=day,
            hour=12,      # 預設中午 12 點
            minute=0,
            tzinfo=zone
        )

        if remind_at < now:
            remind_at = remind_at.replace(year=now.year + 1)

        content = re.sub(r"\d{1,2}/\d{1,2}", "", text).strip()
        if not content:
            content = "未命名行程"

        return remind_at.astimezone(ZoneInfo("UTC")).isoformat(), content

    # ❷ 真的什麼都沒有才放棄
    if not time_match:
        return None

    period, hour = time_match.groups()
    hour = int(hour)

    if period in ("下午", "晚上") and hour < 12:
        hour += 12
    if period in ("早上", "上午") and hour == 12:
        hour = 0


    if weekday_match and time_match:
        weekday_raw = weekday_match.group(2)
        period, hour = time_match.groups()
        hour = int(hour)

        if period in ("下午", "晚上") and hour < 12:
            hour += 12
        if period in ("早上", "上午") and hour == 12:
            hour = 0

        # 支援「禮拜5」
        if weekday_raw.isdigit():
            target_weekday = int(weekday_raw) - 1
        else:
            target_weekday = WEEKDAY_MAP[weekday_raw]

        today_weekday = now.weekday()
        days_ahead = (target_weekday - today_weekday) % 7
        if days_ahead == 0:
            days_ahead = 7

        remind_at = now.replace(
            hour=hour,
            minute=0,
            second=0,
            microsecond=0
        ) + timedelta(days=days_ahead)

        content = re.sub(
            r"(我)?(禮拜|星期)[一二三四五六日天\d]+.*?(點)",
            "",
            text
        ).strip()
        if not content:
            content = "未命名行程"

        return remind_at.astimezone(ZoneInfo("UTC")).isoformat(), content


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

    if remind_at < now and (now - remind_at).days > 180:
        remind_at = remind_at.replace(year=now.year + 1)

    # 只有日期，沒有時間 → 預設中午 12:00
    date_only = re.search(r"(\d{1,2})/(\d{1,2})", text)
    if date_only and not time_match:
        month, day = map(int, date_only.groups())

        remind_at = datetime(
            year=now.year,
            month=month,
            day=day,
            hour=12,
            minute=0,
            tzinfo=zone
        )

        if remind_at < now:
            remind_at = remind_at.replace(year=now.year + 1)

        content = re.sub(r"\d{1,2}/\d{1,2}", "", text).strip()
        return remind_at.astimezone(ZoneInfo("UTC")).isoformat(), content


    content = re.sub(r"(記得)?提醒我", "", text).strip()
    return remind_at.astimezone(ZoneInfo("UTC")).isoformat(), content

@bot.event
async def on_message(message):
    if message.author.bot: return
    await bot.process_commands(message)

    # 判斷是否為私訊或提到 Bot
    if not (isinstance(message.channel, discord.DMChannel) or bot.user in message.mentions):
        return

    user_id = message.author.id
    user_text = message.content.replace(f"<@{bot.user.id}>", "").strip()
    original_text = user_text # 保留原始訊息備用
    
    # 取得使用者時區
    tz = get_user_timezone(user_id) or "Asia/Taipei"

    # --- [1. 短時間計時提醒] ---
    # short_matches = re.findall(
    #     r"(\d+)\s*(秒|分鐘)\s*後?\s*提醒(?:我)?([^，。\n]*)",
    #     user_text
    # )

    # if short_matches:
    #     confirmations = []

    #     for amount, unit, text in short_matches:
    #         delay = int(amount) if unit == "秒" else int(amount) * 60
    #         task_content = text.strip() or "該注意時間囉"

    #         task = asyncio.create_task(
    #             short_timer(bot, delay, task_content, user_id)
    #         )

    #         short_reminder_tasks.setdefault(user_id, []).append({
    #             "content": task_content,
    #             "task": task
    #         })


        #     confirmations.append(f"{amount}{unit}後：{task_content}")

        # # 給 LLM 的「系統事實提示（只加一次）」
        # confirm_text = "、".join(confirmations)
        # user_text += (
        #     f"\n(系統提示：你已成功幫主人設定以下計時提醒：{confirm_text}，"
        #     f"請在回覆中用小說語氣溫柔地確認這件事)"
        # )
    # --- [Agent：自然語言刪除提醒（短提醒 + 排程）] ---
    delete_intent = parse_delete_intent(original_text)
    is_delete = "刪除" in original_text
    delete_intent = parse_delete_intent(original_text) if is_delete else None

    if is_delete:
        delete_intent = delete_intent or {}
        time_hint = delete_intent.get("time_hint")
        content_hint = delete_intent.get("content_hint")

        # 1️⃣ 先嘗試刪除「短時間提醒」
        tasks = short_reminder_tasks.get(user_id, [])
        for t in list(tasks):  # ⚠️ 一定要 list()，避免邊迭代邊刪
            if content_hint and content_hint in t["content"]:
                t["task"].cancel()
                tasks.remove(t)

                if not tasks:
                    short_reminder_tasks.pop(user_id, None)

                await message.channel.send(
                    f"{message.author.mention} 🗑️ 已幫你取消短時間提醒：{t['content']}"
                )
                return
            

        # 2️⃣ 再嘗試刪除「資料庫排程提醒」
        reminders = get_reminders(user_id)
        candidates = []

        for idx, (remind_at, content) in enumerate(reminders, start=1):
            score = 0
            matched_by_time = False


            # 解析 DB 時間（UTC → 使用者時區）
            try:
                dt_utc = datetime.fromisoformat(remind_at)
                if dt_utc.tzinfo is None:
                    dt_utc = dt_utc.replace(tzinfo=ZoneInfo("UTC"))
                dt_local = dt_utc.astimezone(ZoneInfo(tz))
            except Exception:
                continue

            # 🔹 1️⃣ 比對內容
            if content_hint and content and content_hint in content:
                score += 2

            # 🔹 2️⃣ 比對時間（±1 小時視為同一筆）
            if time_hint:
                # 嘗試從 time_hint 解析出時間
                parsed = parse_datetime(time_hint, tz)
                if parsed:
                    target_iso, _ = parsed
                    target_dt = datetime.fromisoformat(target_iso).astimezone(ZoneInfo(tz))

                    if abs((dt_local - target_dt).total_seconds()) <= 3600:
                        score += 1
                else:
                    # 🔹 fallback：只比日期
                    date_hint = re.search(r"(\d{1,2})/(\d{1,2})", time_hint)
                    if date_hint:
                        m, d = map(int, date_hint.groups())
                        if dt_local.month == m and dt_local.day == d:
                            score += 1
            # 🔹 🔥 NEW：如果 LLM 沒給 time_hint，直接從原句抓日期
            if not time_hint:
                # 🔹 🔥 NEW：從原句補抓「早上 / 下午 + 幾點」
                time_match = re.search(
                    r"(早上|上午|下午|晚上)?\s*(\d{1,2})\s*點",
                    original_text
                )

                if time_match:
                    period, h = time_match.groups()
                    h = int(h)

                    if period in ("下午", "晚上") and h < 12:
                        h += 12
                    if period in ("早上", "上午") and h == 12:
                        h = 0

                    # ±1 小時視為同一筆
                    if abs(dt_local.hour - h) <= 1:
                        score += 2
                        matched_by_time = True
                date_hint = re.search(r"(\d{1,2})/(\d{1,2})", original_text)
                if date_hint:
                    m, d = map(int, date_hint.groups())
                    if dt_local.month == m and dt_local.day == d:
                        score += 1

            # ✅ 最終收斂條件：只要有任何一種方式命中，就可刪
            if score > 0 or matched_by_time:
                candidates.append((score, idx, remind_at, content))


        if not candidates:
            await message.channel.send(
                f"{message.author.mention} ⚠️ 我找不到符合描述的提醒，可以再說清楚一點嗎？"
            )
            return

        candidates.sort(reverse=True)
        _, index, remind_at, content = candidates[0]

        delete_reminder_by_index(user_id, index)

        await message.channel.send(
            f"{message.author.mention} 🗑️ 已幫你刪除這個行程：\n"
            f"🕒 {remind_at.replace('T',' ')[:16]}｜{content}"
        )
        return
    clauses = split_into_clauses(original_text)
    confirmations = []

    for clause in clauses:
        intent = parse_reminder_intent(clause)
        if not intent:
            continue

        delay = intent["delay_seconds"]
        content = intent["content"]

        task = asyncio.create_task(
            short_timer(bot, delay, content, user_id)
        )

        short_reminder_tasks.setdefault(user_id, []).append({
            "content": content,
            "task": task
        })

        confirmations.append(f"{delay} 秒後：{content}")

    if confirmations:
        user_text += (
            f"\n(系統提示：你已幫主人設定以下提醒："
            f"{'、'.join(confirmations)}，"
            f"請用溫柔小說語氣確認)"
        )


    



    # --- [Agent：語意型短時間提醒] ---
    # intent = parse_reminder_intent(original_text)

    # if intent:
    #     delay = intent.get("delay_seconds")
    #     content = intent.get("content") or "該注意時間囉"

    #     if delay:
    #         task = asyncio.create_task(
    #             short_timer(bot, delay, content, user_id)
    #         )

    #         short_reminder_tasks.setdefault(user_id, []).append({
    #             "content": content,
    #             "task": task
    #         })

    #         user_text += (
    #             f"\n(系統提示：你已幫主人設定一個約 {delay} 秒後的提醒，"
    #             f"內容是「{content}」，請溫柔地確認這件事)"
    #         )


    # --- [2. 日期排程提醒]：存入 SQLite（一定要在 LLM 前）---
    parsed = parse_datetime(original_text, tz)
    if parsed:
        remind_at, content = parsed
        save_reminder(user_id, remind_at, content)

        await message.channel.send(
            f"{message.author.mention} ✅ 已幫你記下行程：\n"
            f"🕒 {remind_at.replace('T',' ')[:16]}｜{content}"
        )
        return  # 🔥 關鍵：不要再進 LLM


    # --- [3. 生日/紀念日] ---
    anniv_match = re.search(r"(我的)?(生日|紀念日).*?(\d{1,2})/(\d{1,2})", original_text)
    if anniv_match:
        _, kind, month, day = anniv_match.groups()
        save_anniversary(user_id, "birthday" if kind == "生日" else "anniversary", int(month), int(day), kind)
        user_text += f"\n(系統提示：你已記下主人的 {kind} 是 {month} 月 {day} 日)"

    # --- [4. 排程查詢] ---
    if any(k in original_text for k in ["排程", "行程", "有什麼行程"]):
        reminders = get_reminders(user_id)
        role = get_user_role(user_id)
        tz = get_user_timezone(user_id) or "Asia/Taipei"
        reply = render_schedule(reminders, role, tz)
        await message.channel.send(f"{message.author.mention} {reply}")
        return

    # --- [5. 長期記憶與 LLM 生成] ---
    result = should_store_memory(original_text)
    if result and result.get("store"):
        save_memory(user_id, result["category"], result["content"])

    if user_id not in user_history:
        user_history[user_id] = []

    # 傳入經過系統提示修改過的 user_text，確保 LLM 的回答與實際動作一致
    loop = asyncio.get_running_loop()
    reply = await loop.run_in_executor(
        None,
        generate_response,
        user_id,
        user_text,
        user_history[user_id]
    )
    
    user_history[user_id].append({"role": "user", "content": original_text}) # 歷史紀錄存原始文字
    user_history[user_id].append({"role": "assistant", "content": reply})
    
    if len(user_history[user_id]) > 10:
        user_history[user_id] = user_history[user_id][-10:]

    await message.channel.send(f"{message.author.mention} {reply}")

bot.run(TOKEN)