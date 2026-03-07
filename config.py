"""
PW Extractor Bot Configuration - UPDATED
Fixed: Dynamic headers removed (now generated in pw.py)
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Telegram API Credentials
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Bot Settings - OWNER FIXED
OWNER_ID = int(os.getenv("OWNER_ID", "8703802029"))
SUDO_USERS = list(map(int, os.getenv("SUDO_USERS", "").split())) if os.getenv("SUDO_USERS") else []

# Admin IDs = Owner + Sudo Users
ADMIN_IDS = [OWNER_ID] + SUDO_USERS if OWNER_ID else SUDO_USERS

# Database - Optional (if MongoDB fails, bot still works)
MONGO_URL = os.getenv("MONGO_URL", "")
USE_DATABASE = bool(MONGO_URL)  # Will be set to False if connection fails

# Channel Settings
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
PREMIUM_LOGS = int(os.getenv("PREMIUM_LOGS", "0"))

# ==================== PW API CONFIGURATION ====================
PW_ORG_ID = "5eb393ee95fab7468a79d189"
PW_CLIENT_ID = "system-admin"
PW_CLIENT_SECRET = "KjPXuAVfC5xbmgreETNMaL7z"
PW_BASE_URL = "https://api.penpencil.co"

# CRITICAL: Universal Token for Without Login feature
# Get this from a working PW account and set in .env
PW_UNIVERSAL_TOKEN = os.getenv("PW_UNIVERSAL_TOKEN", "")

# NOTE: Headers are now dynamically generated in pw.py
# This ensures randomid and other dynamic fields are fresh per request
