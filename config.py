"""
PW Extractor Bot Configuration - FINAL
Based on databasepw.py
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Telegram API Credentials
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Bot Settings
OWNER_ID = int(os.getenv("OWNER_ID", "8703802029"))
SUDO_USERS = list(map(int, os.getenv("SUDO_USERS", "").split())) if os.getenv("SUDO_USERS") else []
ADMIN_IDS = [OWNER_ID] + SUDO_USERS if OWNER_ID else SUDO_USERS

# Database
MONGO_URL = os.getenv("MONGO_URL", "")
USE_DATABASE = bool(MONGO_URL)

# Channel Settings
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
PREMIUM_LOGS = int(os.getenv("PREMIUM_LOGS", "0"))

# ==================== PW API CONFIGURATION (databasepw.py se) ====================
PW_ORG_ID = "5eb393ee95fab7468a79d189"
PW_CLIENT_ID = "system-admin"
PW_CLIENT_SECRET = "KjPXuAVfC5xbmgreETNMaL7z"
PW_BASE_URL = "https://api.penpencil.co"

# Universal Token for Without Login - set in .env
PW_UNIVERSAL_TOKEN = os.getenv("PW_UNIVERSAL_TOKEN", "")
