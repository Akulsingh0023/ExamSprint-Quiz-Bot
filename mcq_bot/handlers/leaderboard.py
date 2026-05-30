import logging
from typing import List

from telegram import Update
from telegram.ext import ContextTypes

from services import db_service, redis_service

logger = logging.getLogger(__name__)


async def show_leaderboard(chat_id: int, context: ContextTypes.DEFAULT_TYPE, quiz_id: str) -> None:
    results = await db_service.get_leaderboard(quiz_id)
    if not results:
        await context.bot.send_message(chat_id=chat_id, text="No leaderboard data yet.")
        return

    lines: List[str] = ["🏆 LEADERBOARD"]
    for idx, entry in enumerate(results, start=1):
        display_name = entry.get("username") or str(entry.get("user_id"))
        score = entry.get("score", 0)
        total = entry.get("total", 0)
        lines.append(f"{idx}. {display_name} — {score}/{total} ✅")

    await context.bot.send_message(chat_id=chat_id, text="\n".join(lines))


async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat:
        return

    if update.effective_chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Use /leaderboard in the group.")
        return

    group_id = update.effective_chat.id
    quiz_id = await redis_service.get_last_quiz_id(group_id)
    if not quiz_id:
        await update.message.reply_text("No completed quiz yet.")
        return

    await show_leaderboard(group_id, context, quiz_id)
