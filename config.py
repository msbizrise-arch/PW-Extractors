"""
PW Extractor Bot Configuration - FIXED & OPTIMIZED
✅ All environment variables with safe defaults
✅ PW API endpoints & headers properly configured
✅ OWNER_ID, SUDO_USERS, ADMIN_IDS logic fixed
✅ MongoDB optional - bot works even if DB fails
✅ PW Universal Token support for "Without Login" feature
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ====================== TELEGRAM API ======================
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# ====================== BOT OWNERSHIP & ACCESS ======================
# OWNER_ID is critical - must be set correctly
OWNER_ID = int(os.getenv("OWNER_ID", "8703802029"))

# SUDO_USERS: comma-separated list of user IDs with admin access
SUDO_USERS = []
if os.getenv("SUDO_USERS"):
    try:
        SUDO_USERS = list(map(int, os.getenv("SUDO_USERS", "").split(",")))
    except ValueError:
        SUDO_USERS = []

# ADMIN_IDS = Owner + Sudo Users (for premium commands)
ADMIN_IDS = [OWNER_ID] + SUDO_USERS if OWNER_ID else SUDO_USERS

# ====================== DATABASE (Optional) ======================
MONGO_URL = os.getenv("MONGO_URL", "")
# USE_DATABASE will be determined at runtime by plans_db.py
# Bot works with in-memory fallback if MongoDB fails

# ====================== CHANNEL & LOGS ======================
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
PREMIUM_LOGS = int(os.getenv("PREMIUM_LOGS", "0"))

# ====================== PW API CONFIGURATION - CRITICAL ======================
# PW Organization ID (from browser inspect / pw.live API calls)
PW_ORG_ID = os.getenv("PW_ORG_ID", "5eb393ee95fab7468a79d189")

# PW OAuth Client Credentials (for token generation)
PW_CLIENT_ID = os.getenv("PW_CLIENT_ID", "system-admin")
PW_CLIENT_SECRET = os.getenv("PW_CLIENT_SECRET", "KjPXuAVfC5xbmgreETNMaL7z")
# PW API Base URL
PW_BASE_URL = os.getenv("PW_BASE_URL", "https://api.penpencil.co")

# Universal Token for "Without Login" feature (premium users)
# Set via environment variable for security
PW_UNIVERSAL_TOKEN = os.getenv("PW_UNIVERSAL_TOKEN", "")

# ====================== PW API HEADERS - MOBILE CLIENT ======================
# Used for: OTP sending, token generation, my-batches endpoint
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

# ====================== PW API HEADERS - WEB CLIENT ======================
# Used for: Batch search, subject details, content extraction
PW_WEB_HEADERS = {
    "Host": "api.penpencil.co",
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9",
    "client-id": PW_ORG_ID,
    "client-type": "WEB",
    "client-version": "2.6.12",
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

# ====================== RATE LIMITING & TIMEOUTS ======================
# API request timeout (seconds)
PW_API_TIMEOUT = int(os.getenv("PW_API_TIMEOUT", "20"))

# Delay between API calls to avoid rate limiting (seconds)
PW_API_DELAY = float(os.getenv("PW_API_DELAY", "0.3"))

# Max pages to fetch for batch/content search
PW_MAX_PAGES = int(os.getenv("PW_MAX_PAGES", "10"))
# ====================== EXTRACTION SETTINGS ======================
# Max subjects to extract in one batch (prevents timeout)
MAX_SUBJECTS_PER_BATCH = int(os.getenv("MAX_SUBJECTS_PER_BATCH", "20"))

# Output file encoding
OUTPUT_ENCODING = os.getenv("OUTPUT_ENCODING", "utf-8")

# ====================== LOGGING ======================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FILE = os.getenv("LOG_FILE", "bot.log")

# ====================== VALIDATION ======================
def validate_config():
    """Validate critical configuration values."""
    errors = []
    
    if not API_ID or API_ID == 0:
        errors.append("API_ID not set or invalid")
    if not API_HASH:
        errors.append("API_HASH not set")
    if not BOT_TOKEN:
        errors.append("BOT_TOKEN not set")
    if not OWNER_ID or OWNER_ID == 0:
        errors.append("OWNER_ID not set or invalid")
    if not PW_ORG_ID:
        errors.append("PW_ORG_ID not set")
    
    if errors:
        print("⚠️ Configuration Warnings:")
        for err in errors:
            print(f"  • {err}")
        print("Bot may not work correctly. Check environment variables.")
        return False
    return True

# Run validation on import
if __name__ != "__main__":
    validate_config()
