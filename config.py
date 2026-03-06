import os
from dotenv import load_dotenv

load_dotenv()

# Telegram API Credentials
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Bot Settings
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
SUDO_USERS = list(map(int, os.getenv("SUDO_USERS", "").split())) if os.getenv("SUDO_USERS") else []

# Admin IDs = Owner + Sudo Users (used by plans module)
ADMIN_IDS = []
if OWNER_ID and OWNER_ID != 0:
    ADMIN_IDS.append(OWNER_ID)
ADMIN_IDS.extend(SUDO_USERS)

# Database
MONGO_URL = os.getenv("MONGO_URL", "")

# Channel Settings
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))  # Force subscribe channel
PREMIUM_LOGS = int(os.getenv("PREMIUM_LOGS", "0"))  # Premium logs channel

# PW API Constants
PW_ORG_ID = "5eb393ee95fab7468a79d189"
PW_CLIENT_SECRET = "KjPXuAVfC5xbmgreETNMaL7z"
PW_BASE_URL = "https://api.penpencil.co"

# PW Universal Token for Without Login feature
# Set this env var to a working PW bearer token for no-login batch access
PW_UNIVERSAL_TOKEN = os.getenv("PW_UNIVERSAL_TOKEN", "")
