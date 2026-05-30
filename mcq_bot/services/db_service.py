import logging
from datetime import datetime, timezone
from typing import Dict, List

from motor.motor_asyncio import AsyncIOMotorClient

from config import DB_NAME, MONGODB_URI

logger = logging.getLogger(__name__)

_client = AsyncIOMotorClient(MONGODB_URI)
_db = _client[DB_NAME]
_results = _db["quiz_results"]


async def save_result(quiz_id: str, user_id: int, username: str, score: int, total: int) -> None:
    percentage = round((score / total) * 100, 2) if total else 0.0
    payload = {
        "quiz_id": quiz_id,
        "user_id": user_id,
        "username": username,
        "score": score,
        "total": total,
        "percentage": percentage,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        await _results.insert_one(payload)
    except Exception:
        logger.exception("Failed to save result for user %s", user_id)


async def get_leaderboard(quiz_id: str) -> List[Dict]:
    try:
        cursor = _results.find({"quiz_id": quiz_id}).sort("score", -1)
        return [doc async for doc in cursor]
    except Exception:
        logger.exception("Failed to fetch leaderboard for quiz %s", quiz_id)
        return []


async def get_user_history(user_id: int) -> List[Dict]:
    try:
        cursor = _results.find({"user_id": user_id}).sort("completed_at", -1)
        return [doc async for doc in cursor]
    except Exception:
        logger.exception("Failed to fetch user history for %s", user_id)
        return []
