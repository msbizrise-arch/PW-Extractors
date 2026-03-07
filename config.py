import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
SUDO_USERS = list(map(int, os.getenv("SUDO_USERS", "").split())) if os.getenv("SUDO_USERS") else []
MONGO_URL = os.getenv("MONGO_URL", "")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0")) if os.getenv("CHANNEL_ID") else 0
PREMIUM_LOGS = int(os.getenv("PREMIUM_LOGS", "0")) if os.getenv("PREMIUM_LOGS") else 0

# Combine OWNER_ID and SUDO_USERS for admin access
ADMIN_IDS = list(set(SUDO_USERS + ([OWNER_ID] if OWNER_ID else [])))
