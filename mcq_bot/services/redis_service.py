import json
import logging
from typing import Any, Dict, List, Optional

import redis.asyncio as redis

from config import REDIS_URL

logger = logging.getLogger(__name__)

REDIS_CLIENT = redis.from_url(REDIS_URL, decode_responses=True)

SESSION_PREFIX = "quiz_session:"
QUIZ_CONFIG_KEY = "quiz_config"
PENDING_QUIZ_PREFIX = "pending_quiz:"
JOINERS_PREFIX = "quiz_joiners:"
JOINING_PREFIX = "quiz_joining_active:"
CURRENT_QUIZ_PREFIX = "current_quiz_id:"
LAST_QUIZ_PREFIX = "last_quiz_id:"
GROUP_QUIZ_PREFIX = "group_quiz_state:"
POLL_GROUP_PREFIX = "poll_group:"
QUIZ_SCORES_PREFIX = "quiz_scores:"
QUIZ_USERS_PREFIX = "quiz_users:"
QUIZ_USERNAMES_PREFIX = "quiz_usernames:"
GROUPS_SET_KEY = "registered_groups"
GROUP_TITLES_HASH = "group_titles"


def _session_key(user_id: int) -> str:
    return f"{SESSION_PREFIX}{user_id}"


def _pending_key(group_id: int) -> str:
    return f"{PENDING_QUIZ_PREFIX}{group_id}"


def _joiners_key(group_id: int) -> str:
    return f"{JOINERS_PREFIX}{group_id}"


def _joining_key(group_id: int) -> str:
    return f"{JOINING_PREFIX}{group_id}"


def _current_quiz_key(group_id: int) -> str:
    return f"{CURRENT_QUIZ_PREFIX}{group_id}"


def _last_quiz_key(group_id: int) -> str:
    return f"{LAST_QUIZ_PREFIX}{group_id}"


def _group_quiz_key(group_id: int) -> str:
    return f"{GROUP_QUIZ_PREFIX}{group_id}"


def _poll_group_key(poll_id: str) -> str:
    return f"{POLL_GROUP_PREFIX}{poll_id}"


def _quiz_scores_key(quiz_id: str) -> str:
    return f"{QUIZ_SCORES_PREFIX}{quiz_id}"


def _quiz_users_key(quiz_id: str) -> str:
    return f"{QUIZ_USERS_PREFIX}{quiz_id}"


def _quiz_usernames_key(quiz_id: str) -> str:
    return f"{QUIZ_USERNAMES_PREFIX}{quiz_id}"


def _rate_limit_key(user_id: int) -> str:
    return f"join_rate:{user_id}"


async def create_session(user_id: int, questions: List[Dict[str, Any]], timer: int, quiz_id: str) -> None:
    session = {
        "questions": questions,
        "current_index": 0,
        "score": 0,
        "timer_seconds": timer,
        "total_questions": len(questions),
        "answered_current": False,
        "poll_message_id": None,
        "poll_id": None,
        "quiz_id": quiz_id,
    }
    try:
        await REDIS_CLIENT.set(_session_key(user_id), json.dumps(session))
    except Exception:
        logger.exception("Failed to create session for user %s", user_id)


async def get_session(user_id: int) -> Optional[Dict[str, Any]]:
    try:
        raw = await REDIS_CLIENT.get(_session_key(user_id))
    except Exception:
        logger.exception("Failed to fetch session for user %s", user_id)
        return None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.exception("Failed to decode session for user %s", user_id)
        return None


async def update_session(user_id: int, data: Dict[str, Any]) -> None:
    session = await get_session(user_id)
    if not session:
        return
    session.update(data)
    try:
        await REDIS_CLIENT.set(_session_key(user_id), json.dumps(session))
    except Exception:
        logger.exception("Failed to update session for user %s", user_id)


async def delete_session(user_id: int) -> None:
    try:
        await REDIS_CLIENT.delete(_session_key(user_id))
    except Exception:
        logger.exception("Failed to delete session for user %s", user_id)


async def register_group(group_id: int, title: str) -> None:
    try:
        await REDIS_CLIENT.sadd(GROUPS_SET_KEY, str(group_id))
        await REDIS_CLIENT.hset(GROUP_TITLES_HASH, str(group_id), title)
    except Exception:
        logger.exception("Failed to register group %s", group_id)


async def list_groups() -> List[Dict[str, Any]]:
    try:
        group_ids = await REDIS_CLIENT.smembers(GROUPS_SET_KEY)
    except Exception:
        logger.exception("Failed to list groups")
        return []
    results: List[Dict[str, Any]] = []
    for group_id in group_ids:
        title = await get_group_title(int(group_id))
        results.append({"id": int(group_id), "title": title})
    return sorted(results, key=lambda item: item["title"] or str(item["id"]))


async def get_group_title(group_id: int) -> str:
    try:
        return await REDIS_CLIENT.hget(GROUP_TITLES_HASH, str(group_id)) or str(group_id)
    except Exception:
        logger.exception("Failed to read group title for %s", group_id)
        return str(group_id)


async def set_quiz_config(data: Dict[str, Any]) -> None:
    try:
        await REDIS_CLIENT.set(QUIZ_CONFIG_KEY, json.dumps(data))
    except Exception:
        logger.exception("Failed to set quiz config")


async def get_quiz_config() -> Optional[Dict[str, Any]]:
    try:
        raw = await REDIS_CLIENT.get(QUIZ_CONFIG_KEY)
    except Exception:
        logger.exception("Failed to get quiz config")
        return None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.exception("Failed to decode quiz config")
        return None


async def clear_quiz_config() -> None:
    try:
        await REDIS_CLIENT.delete(QUIZ_CONFIG_KEY)
    except Exception:
        logger.exception("Failed to clear quiz config")


async def set_pending_quiz(group_id: int, data: Dict[str, Any]) -> None:
    try:
        await REDIS_CLIENT.set(_pending_key(group_id), json.dumps(data))
    except Exception:
        logger.exception("Failed to set pending quiz for group %s", group_id)


async def get_pending_quiz(group_id: int) -> Optional[Dict[str, Any]]:
    try:
        raw = await REDIS_CLIENT.get(_pending_key(group_id))
    except Exception:
        logger.exception("Failed to get pending quiz for group %s", group_id)
        return None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.exception("Failed to decode pending quiz for group %s", group_id)
        return None


async def clear_pending_quiz(group_id: int) -> None:
    try:
        await REDIS_CLIENT.delete(_pending_key(group_id))
    except Exception:
        logger.exception("Failed to clear pending quiz for group %s", group_id)


async def set_joining_active(group_id: int, seconds: int) -> None:
    try:
        await REDIS_CLIENT.set(_joining_key(group_id), "1", ex=seconds)
    except Exception:
        logger.exception("Failed to set joining flag for group %s", group_id)


async def is_joining_active(group_id: int) -> bool:
    try:
        return bool(await REDIS_CLIENT.get(_joining_key(group_id)))
    except Exception:
        logger.exception("Failed to read joining flag for group %s", group_id)
        return False


async def clear_joiners(group_id: int) -> None:
    try:
        await REDIS_CLIENT.delete(_joiners_key(group_id))
    except Exception:
        logger.exception("Failed to clear joiners for group %s", group_id)


async def joiner_count(group_id: int) -> int:
    try:
        return int(await REDIS_CLIENT.scard(_joiners_key(group_id)))
    except Exception:
        logger.exception("Failed to count joiners for group %s", group_id)
        return 0


async def add_joiner(group_id: int, user_id: int) -> None:
    try:
        await REDIS_CLIENT.sadd(_joiners_key(group_id), str(user_id))
    except Exception:
        logger.exception("Failed to add joiner %s for group %s", user_id, group_id)


async def is_joiner(group_id: int, user_id: int) -> bool:
    try:
        return await REDIS_CLIENT.sismember(_joiners_key(group_id), str(user_id))
    except Exception:
        logger.exception("Failed to check joiner %s for group %s", user_id, group_id)
        return False


async def get_joiners(group_id: int) -> List[int]:
    try:
        values = await REDIS_CLIENT.smembers(_joiners_key(group_id))
    except Exception:
        logger.exception("Failed to fetch joiners for group %s", group_id)
        return []
    return [int(value) for value in values if str(value).isdigit()]


async def set_current_quiz_id(group_id: int, quiz_id: str) -> None:
    try:
        await REDIS_CLIENT.set(_current_quiz_key(group_id), quiz_id)
        await REDIS_CLIENT.set(_last_quiz_key(group_id), quiz_id)
    except Exception:
        logger.exception("Failed to set current quiz id for group %s", group_id)


async def get_current_quiz_id(group_id: int) -> Optional[str]:
    try:
        return await REDIS_CLIENT.get(_current_quiz_key(group_id))
    except Exception:
        logger.exception("Failed to get current quiz id for group %s", group_id)
        return None


async def clear_current_quiz_id(group_id: int) -> None:
    try:
        await REDIS_CLIENT.delete(_current_quiz_key(group_id))
    except Exception:
        logger.exception("Failed to clear current quiz id for group %s", group_id)


async def get_last_quiz_id(group_id: int) -> Optional[str]:
    try:
        return await REDIS_CLIENT.get(_last_quiz_key(group_id))
    except Exception:
        logger.exception("Failed to get last quiz id for group %s", group_id)
        return None


async def set_group_quiz_state(group_id: int, state: Dict[str, Any]) -> None:
    try:
        await REDIS_CLIENT.set(_group_quiz_key(group_id), json.dumps(state))
    except Exception:
        logger.exception("Failed to set group quiz state for group %s", group_id)


async def get_group_quiz_state(group_id: int) -> Optional[Dict[str, Any]]:
    try:
        raw = await REDIS_CLIENT.get(_group_quiz_key(group_id))
    except Exception:
        logger.exception("Failed to get group quiz state for group %s", group_id)
        return None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.exception("Failed to decode group quiz state for group %s", group_id)
        return None


async def update_group_quiz_state(group_id: int, data: Dict[str, Any]) -> None:
    state = await get_group_quiz_state(group_id)
    if not state:
        return
    state.update(data)
    try:
        await REDIS_CLIENT.set(_group_quiz_key(group_id), json.dumps(state))
    except Exception:
        logger.exception("Failed to update group quiz state for group %s", group_id)


async def clear_group_quiz_state(group_id: int) -> None:
    try:
        await REDIS_CLIENT.delete(_group_quiz_key(group_id))
    except Exception:
        logger.exception("Failed to clear group quiz state for group %s", group_id)


async def set_poll_group(poll_id: str, group_id: int, ttl_seconds: int = 3600) -> None:
    try:
        await REDIS_CLIENT.set(_poll_group_key(poll_id), str(group_id), ex=ttl_seconds)
    except Exception:
        logger.exception("Failed to set poll group for %s", poll_id)


async def get_poll_group(poll_id: str) -> Optional[int]:
    try:
        value = await REDIS_CLIENT.get(_poll_group_key(poll_id))
    except Exception:
        logger.exception("Failed to get poll group for %s", poll_id)
        return None
    return int(value) if value else None


async def clear_poll_group(poll_id: str) -> None:
    try:
        await REDIS_CLIENT.delete(_poll_group_key(poll_id))
    except Exception:
        logger.exception("Failed to clear poll group for %s", poll_id)


async def add_quiz_user(quiz_id: str, user_id: int) -> None:
    try:
        await REDIS_CLIENT.sadd(_quiz_users_key(quiz_id), str(user_id))
    except Exception:
        logger.exception("Failed to add quiz user %s", user_id)


async def is_quiz_user(quiz_id: str, user_id: int) -> bool:
    try:
        return await REDIS_CLIENT.sismember(_quiz_users_key(quiz_id), str(user_id))
    except Exception:
        logger.exception("Failed to check quiz user %s", user_id)
        return False


async def get_quiz_users(quiz_id: str) -> List[int]:
    try:
        values = await REDIS_CLIENT.smembers(_quiz_users_key(quiz_id))
    except Exception:
        logger.exception("Failed to get quiz users")
        return []
    return [int(value) for value in values if str(value).isdigit()]


async def quiz_user_count(quiz_id: str) -> int:
    try:
        return int(await REDIS_CLIENT.scard(_quiz_users_key(quiz_id)))
    except Exception:
        logger.exception("Failed to count quiz users")
        return 0


async def clear_quiz_users(quiz_id: str) -> None:
    try:
        await REDIS_CLIENT.delete(_quiz_users_key(quiz_id))
    except Exception:
        logger.exception("Failed to clear quiz users")


async def increment_quiz_score(quiz_id: str, user_id: int) -> None:
    try:
        await REDIS_CLIENT.hincrby(_quiz_scores_key(quiz_id), str(user_id), 1)
    except Exception:
        logger.exception("Failed to increment quiz score for %s", user_id)


async def get_quiz_scores(quiz_id: str) -> Dict[str, str]:
    try:
        return await REDIS_CLIENT.hgetall(_quiz_scores_key(quiz_id))
    except Exception:
        logger.exception("Failed to get quiz scores")
        return {}


async def get_quiz_score(quiz_id: str, user_id: int) -> int:
    try:
        value = await REDIS_CLIENT.hget(_quiz_scores_key(quiz_id), str(user_id))
    except Exception:
        logger.exception("Failed to get quiz score for %s", user_id)
        return 0
    return int(value or 0)


async def clear_quiz_scores(quiz_id: str) -> None:
    try:
        await REDIS_CLIENT.delete(_quiz_scores_key(quiz_id))
    except Exception:
        logger.exception("Failed to clear quiz scores")


async def set_quiz_username(quiz_id: str, user_id: int, username: str) -> None:
    try:
        await REDIS_CLIENT.hset(_quiz_usernames_key(quiz_id), str(user_id), username)
    except Exception:
        logger.exception("Failed to set quiz username for %s", user_id)


async def get_quiz_username(quiz_id: str, user_id: int) -> Optional[str]:
    try:
        return await REDIS_CLIENT.hget(_quiz_usernames_key(quiz_id), str(user_id))
    except Exception:
        logger.exception("Failed to get quiz username for %s", user_id)
        return None


async def clear_quiz_usernames(quiz_id: str) -> None:
    try:
        await REDIS_CLIENT.delete(_quiz_usernames_key(quiz_id))
    except Exception:
        logger.exception("Failed to clear quiz usernames")


async def rate_limit_join(user_id: int, window_seconds: int = 5) -> bool:
    try:
        created = await REDIS_CLIENT.set(_rate_limit_key(user_id), "1", ex=window_seconds, nx=True)
        return bool(created)
    except Exception:
        logger.exception("Failed to rate limit user %s", user_id)
        return True
