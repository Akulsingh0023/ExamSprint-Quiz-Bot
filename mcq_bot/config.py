import logging
import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip() or None

ADMIN_USER_IDS = [
    int(user_id.strip())
    for user_id in os.getenv("ADMIN_USER_IDS", "").split(",")
    if user_id.strip().isdigit()
]

GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "0").strip() or 0)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379").strip()
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017").strip()
DB_NAME = os.getenv("DB_NAME", "mcq_bot").strip()
JOIN_WINDOW_SECONDS = int(os.getenv("JOIN_WINDOW_SECONDS", "60").strip() or 60)

logging.getLogger(__name__).info("Config loaded")
