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


def render_schedule(reminders, role, mode="all"):
    if not reminders:
        return "📭 目前沒有任何行程。"

    # ======================
    # 角色口吻
    # ======================
    if role == "secretary":
        prefix = "📋 行程摘要如下："
    elif role == "maid":
        prefix = "主人～這是您接下來的安排 💕"
    else:
        prefix = "這是你目前的行程 ❤️"

    lines = []

    for r in reminders:
        # 支援 tuple / dict
        remind_at = _get_field(r, "remind_at", 0)
        content = _get_field(r, "content", 1)

        # 格式化時間（安全）
        try:
            time_str = remind_at.replace("T", " ")[:16]
        except Exception:
            time_str = str(remind_at)

        lines.append(f"🕒 {time_str}｜{content}")

    # ======================
    # 模式補充（today / week）
    # ======================
    if mode == "today":
        title = "📆 今日行程"
    elif mode == "week":
        title = "⏳ 本週行程"
    else:
        title = "📅 行程列表"

    return f"{title}\n{prefix}\n" + "\n".join(lines)

def render_schedule_embed(reminders, role, title="📅 行程摘要"):
    embed = discord.Embed(
        title=title,
        color=0xF4A7B9 if role == "maid" else 0x6C9BCF
    )

    if not reminders:
        embed.description = "📭 目前沒有任何行程。"
        return embed

    # 角色描述
    if role == "secretary":
        embed.description = "以下是您目前的重要行程："
    elif role == "maid":
        embed.description = "主人～這是您接下來的安排唷 💕"
    else:
        embed.description = "這是你接下來需要注意的事情 ❤️"

    for r in reminders:
        remind_at = r[0].replace("T", " ")[:16]
        content = r[1]
        embed.add_field(
            name=f"🕒 {remind_at}",
            value=content,
            inline=False
        )

    embed.set_footer(text="你的貼身助理正在替你記著 ✨")
    return embed
