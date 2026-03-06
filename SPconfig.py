"""
PW Extractor Bot Configuration
Fixed: All settings, OWNER_ID, API constants
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

# PW Universal Token (for without login feature)
PW_UNIVERSAL_TOKEN = os.getenv("PW_UNIVERSAL_TOKEN", "")

# PW API Headers - MOBILE (for OTP/Login)
PW_MOBILE_HEADERS = {
    "Host": "api.penpencil.co",
    "accept": "application/json",
    "client-id": PW_ORG_ID,
    "client-type": "MOBILE",
    "client-version": "12.84",
    "user-agent": "Android",
    "randomid": "e4307177362e86f1",
    "content-type": "application/json",
}

# PW API Headers - WEB (for batch fetching)
PW_WEB_HEADERS = {
    "Host": "api.penpencil.co",
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9",
    "client-id": PW_ORG_ID,
    "client-type": "WEB",
    "client-version": "6.0.0",
    "content-type": "application/json",
    "origin": "https://www.pw.live",
    "referer": "https://www.pw.live/",
    "sec-ch-ua": '"Not_A Brand";v="99", "Google Chrome";v="109", "Chromium";v="109"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Linux"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "cross-site",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
}
