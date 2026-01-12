from datetime import datetime
from zoneinfo import ZoneInfo
import discord


def _get_field(row, key, index):
    """
    同時支援 tuple 與 dict
    """
    if isinstance(row, dict):
        return row.get(key)
    return row[index]


def _format_time(remind_at, user_timezone):
    """
    將 UTC ISO 字串轉為使用者時區顯示
    """
    try:
        dt_utc = datetime.fromisoformat(remind_at)
        if dt_utc.tzinfo is None:
            dt_utc = dt_utc.replace(tzinfo=ZoneInfo("UTC"))

        dt_local = dt_utc.astimezone(ZoneInfo(user_timezone))
        return dt_local.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(remind_at)


def render_schedule(reminders, role, user_timezone="Asia/Taipei", mode="all"):
    if not reminders:
        return "📭 目前沒有任何行程。"

    if role == "secretary":
        prefix = "📋 行程摘要如下："
    elif role == "maid":
        prefix = "這是您接下來的安排 💕"
    else:
        prefix = "這是你目前的行程 ❤️"

    lines = []

    for r in reminders:
        remind_at = _get_field(r, "remind_at", 0)
        content = _get_field(r, "content", 1)

        time_str = _format_time(remind_at, user_timezone)
        lines.append(f"🕒 {time_str}｜{content}")

    if mode == "today":
        title = "📆 今日行程"
    elif mode == "week":
        title = "⏳ 本週行程"
    else:
        title = "📅 行程列表"

    return f"{title}\n{prefix}\n" + "\n".join(lines)


def render_schedule_embed(reminders, role, user_timezone="Asia/Taipei", title="📅 行程摘要"):
    embed = discord.Embed(
        title=title,
        color=0xF4A7B9 if role == "maid" else 0x6C9BCF
    )

    if not reminders:
        embed.description = "📭 目前沒有任何行程。"
        return embed

    if role == "secretary":
        embed.description = "以下是您目前的重要行程："
    elif role == "maid":
        embed.description = "這是您接下來的安排唷 💕"
    else:
        embed.description = "這是你接下來需要注意的事情 ❤️"

    for r in reminders:
        remind_at = _get_field(r, "remind_at", 0)
        content = _get_field(r, "content", 1)

        time_str = _format_time(remind_at, user_timezone)

        embed.add_field(
            name=f"🕒 {time_str}",
            value=content,
            inline=False
        )

    embed.set_footer(text="你的貼身助理正在替你記著 ✨")
    return embed