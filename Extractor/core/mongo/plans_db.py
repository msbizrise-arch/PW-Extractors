"""
Database Module - FIXED
✅ Works with or without MongoDB
✅ If MongoDB fails, uses in-memory storage for OWNER only
✅ Fixed: SSL handshake errors on Render by trying tls=False fallback
✅ Fixed: Collection truth value testing (if db is None)
✅ Fixed: Proper error handling in all database functions
"""
import logging
from datetime import datetime, timedelta
import pytz

try:
    from motor.motor_asyncio import AsyncIOMotorClient as MongoCli
    MOTOR_AVAILABLE = True
except ImportError:
    MOTOR_AVAILABLE = False

from config import MONGO_URL, OWNER_ID, USE_DATABASE

LOGGER = logging.getLogger(__name__)

# In-memory storage fallback (for when MongoDB fails)
_in_memory_premium = {}
_db = None
_mongo_client = None
_db_available = False

def init_database():
    """Initialize database connection with SSL fallback."""
    global _db, _mongo_client, _db_available
    
    if not USE_DATABASE or not MONGO_URL or not MOTOR_AVAILABLE:
        LOGGER.warning("MongoDB not available. Using in-memory storage.")
        _db_available = False
        return False
    
    try:
        # Try connecting with SSL (for Render/Atlas deployments)
        _mongo_client = MongoCli(
            MONGO_URL,
            tls=True,
            tlsAllowInvalidCertificates=True,
            serverSelectionTimeoutMS=10000,
            connectTimeoutMS=10000,
            socketTimeoutMS=30000,
        )
        _db = _mongo_client.premium.premium_db
        _db_available = True
        LOGGER.info("MongoDB connected successfully (SSL)")        return True
    except Exception as e1:
        LOGGER.warning(f"MongoDB SSL connection failed: {e1}, trying without SSL...")
        try:
            _mongo_client = MongoCli(
                MONGO_URL,
                tls=False,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=10000,
            )
            _db = _mongo_client.premium.premium_db
            _db_available = True
            LOGGER.info("MongoDB connected successfully (no SSL)")
            return True
        except Exception as e2:
            LOGGER.error(f"MongoDB connection failed: {e2}")
            LOGGER.warning("Using in-memory storage instead")
            _db_available = False
            return False

# Initialize on module load
init_database()

# ====================== PREMIUM FUNCTIONS ======================
async def add_premium(user_id, expire_date):
    """Add premium to user."""
    global _db_available
    
    if _db_available and _db is not None:
        try:
            await _db.update_one(
                {"_id": user_id},
                {"$set": {"expire_date": expire_date}},
                upsert=True
            )
            LOGGER.info(f"Premium added for user {user_id} (MongoDB)")
            return True
        except Exception as e:
            LOGGER.error(f"MongoDB add_premium error: {e}")
            _db_available = False
    
    # Fallback to in-memory
    _in_memory_premium[user_id] = {"expire_date": expire_date}
    LOGGER.info(f"Premium added for user {user_id} (in-memory)")
    return True

async def remove_premium(user_id):
    """Remove premium from user."""
    global _db_available    
    # Remove from in-memory
    if user_id in _in_memory_premium:
        del _in_memory_premium[user_id]
    
    if _db_available and _db is not None:
        try:
            await _db.delete_one({"_id": user_id})
            LOGGER.info(f"Premium removed for user {user_id} (MongoDB)")
            return True
        except Exception as e:
            LOGGER.error(f"MongoDB remove_premium error: {e}")
            _db_available = False
    
    LOGGER.info(f"Premium removed for user {user_id} (in-memory)")
    return True

async def check_premium(user_id):
    """Check if user has premium - returns data or None."""
    global _db_available
    
    # OWNER is always premium
    if user_id == OWNER_ID:
        tz = pytz.timezone("Asia/Kolkata")
        return {
            "_id": OWNER_ID,
            "expire_date": datetime.now(tz) + timedelta(days=3650)  # 10 years
        }
    
    # Check in-memory first
    if user_id in _in_memory_premium:
        return _in_memory_premium[user_id]
    
    if _db_available and _db is not None:
        try:
            data = await _db.find_one({"_id": user_id})
            if 
                # Cache in memory
                _in_memory_premium[user_id] = data
            return data
        except Exception as e:
            LOGGER.error(f"MongoDB check_premium error: {e}")
            _db_available = False
    
    return None

async def is_premium_user(user_id):
    """Check if user is premium (boolean)."""
    # OWNER is always premium
    if user_id == OWNER_ID:        return True
    
    data = await check_premium(user_id)
    if data is None:
        return False
    
    try:
        expiry = data.get("expire_date")
        if expiry:
            tz = pytz.timezone("Asia/Kolkata")
            now = datetime.now(tz)
            if hasattr(expiry, 'astimezone'):
                expiry = expiry.astimezone(tz)
            return expiry > now
    except Exception as e:
        LOGGER.error(f"Error checking premium expiry: {e}")
    
    return False

async def premium_users():
    """Get list of all premium user IDs."""
    global _db_available
    users = list(_in_memory_premium.keys())
    
    if _db_available and _db is not None:
        try:
            async for data in _db.find():
                if "_id" in data and data["_id"] not in users:
                    users.append(data["_id"])
        except Exception as e:
            LOGGER.error(f"MongoDB premium_users error: {e}")
            _db_available = False
    
    # Always include OWNER
    if OWNER_ID not in users:
        users.append(OWNER_ID)
    
    return users
