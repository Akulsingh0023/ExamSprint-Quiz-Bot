import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes

from services import db_service, redis_service

logger = logging.getLogger(__name__)


async def join_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        target_chat = query.message
        user = query.from_user
        if not target_chat or not user:
            return
        if target_chat.chat.type not in ("group", "supergroup"):
            await query.edit_message_text("Use /join inside a group.")
            return
        group_id = target_chat.chat.id
        reply = target_chat.reply_text
    else:
        if not update.effective_user or not update.message:
            return
        if not update.effective_chat or update.effective_chat.type not in ("group", "supergroup"):
            await update.message.reply_text("Use /join inside a group.")
            return
        group_id = update.effective_chat.id
        user = update.effective_user
        reply = update.message.reply_text

    if not await redis_service.is_joining_active(group_id):
        await reply("No quiz is active right now.")
        return

    if not await redis_service.rate_limit_join(user.id):
        await reply("Please wait a moment before trying again.")
        return

    if await redis_service.is_joiner(group_id, user.id):
        await reply("You're already in!")
        return

    await redis_service.add_joiner(group_id, user.id)
    await reply("✅ You're in! Quiz starts soon. Get ready.")


async def send_group_question(context: ContextTypes.DEFAULT_TYPE, group_id: int) -> None:
    state = await redis_service.get_group_quiz_state(group_id)
    if not state:
        return

    index = int(state.get("current_index", 0))
    total = int(state.get("total_questions", 0))
    question = state["questions"][index]
    question_text = question["question"]
    options = question["options"]
    correct_index = int(question["correct_index"])
    timer_seconds = int(state.get("timer_seconds", 10))

    message = await context.bot.send_poll(
        chat_id=group_id,
        question=f"Q{index + 1}/{total}: {question_text}",
        options=options,
        type="quiz",
        correct_option_id=correct_index,
        open_period=timer_seconds,
        is_anonymous=False,
        explanation=f"Correct answer: {options[correct_index]}",
    )

    await redis_service.update_group_quiz_state(
        group_id,
        {"poll_id": message.poll.id, "poll_message_id": message.message_id},
    )
    await redis_service.set_poll_group(message.poll.id, group_id)

    asyncio.create_task(_group_fallback(context, group_id, timer_seconds + 1, message.poll.id))


async def _group_fallback(
    context: ContextTypes.DEFAULT_TYPE,
    group_id: int,
    delay_seconds: int,
    poll_id: str,
) -> None:
    await asyncio.sleep(delay_seconds)
    state = await redis_service.get_group_quiz_state(group_id)
    if not state:
        return
    if state.get("poll_id") != poll_id:
        return

    await advance_group_question(context, group_id)


async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.poll_answer:
        return

    poll_id = update.poll_answer.poll_id
    group_id = await redis_service.get_poll_group(poll_id)
    if not group_id:
        return

    state = await redis_service.get_group_quiz_state(group_id)
    if not state or state.get("poll_id") != poll_id:
        return

    quiz_id = state["quiz_id"]
    user = update.poll_answer.user
    if not await redis_service.is_quiz_user(quiz_id, user.id):
        return

    display_name = f"@{user.username}" if user.username else (user.full_name or str(user.id))
    await redis_service.set_quiz_username(quiz_id, user.id, display_name)

    selected_ids = update.poll_answer.option_ids
    if selected_ids:
        selected = selected_ids[0]
        current_index = int(state.get("current_index", 0))
        question = state["questions"][current_index]
        if selected == int(question["correct_index"]):
            await redis_service.increment_quiz_score(quiz_id, user.id)


async def advance_group_question(context: ContextTypes.DEFAULT_TYPE, group_id: int) -> None:
    state = await redis_service.get_group_quiz_state(group_id)
    if not state:
        return

    current_index = int(state.get("current_index", 0)) + 1
    total = int(state.get("total_questions", 0))

    await redis_service.update_group_quiz_state(
        group_id,
        {"current_index": current_index, "poll_id": None, "poll_message_id": None},
    )

    if current_index >= total:
        await finish_group_quiz(context, group_id)
        return

    await send_group_question(context, group_id)


async def finish_group_quiz(context: ContextTypes.DEFAULT_TYPE, group_id: int) -> None:
    state = await redis_service.get_group_quiz_state(group_id)
    if not state:
        return

    quiz_id = state["quiz_id"]
    total = int(state.get("total_questions", 0))

    user_ids = await redis_service.get_quiz_users(quiz_id)
    if not user_ids:
        await redis_service.clear_group_quiz_state(group_id)
        await redis_service.clear_current_quiz_id(group_id)
        return

    lines = ["🎉 Quiz Complete! Results:"]
    for user_id in user_ids:
        score = await redis_service.get_quiz_score(quiz_id, user_id)
        percentage = round((score / total) * 100, 2) if total else 0.0
        display_name = await redis_service.get_quiz_username(quiz_id, user_id) or str(user_id)
        await db_service.save_result(quiz_id, user_id, display_name, score, total)
        lines.append(f"{display_name}: {score}/{total} ({percentage}%)")

    await context.bot.send_message(chat_id=group_id, text="\n".join(lines))

    from handlers.leaderboard import show_leaderboard

    await show_leaderboard(group_id, context, quiz_id)

    await redis_service.clear_group_quiz_state(group_id)
    await redis_service.clear_quiz_scores(quiz_id)
    await redis_service.clear_quiz_users(quiz_id)
    await redis_service.clear_quiz_usernames(quiz_id)
    await redis_service.clear_current_quiz_id(group_id)
