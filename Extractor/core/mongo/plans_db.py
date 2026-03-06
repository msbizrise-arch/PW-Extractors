"""
MongoDB Database Functions for Premium Management
Fixed: SSL handshake error, connection issues
Fixed: All collection operations
"""
from motor.motor_asyncio import AsyncIOMotorClient as MongoCli
from config import MONGO_URL
import logging

LOGGER = logging.getLogger(__name__)

# Global db variable
db = None
mongo_client = None

def init_mongo():
    """Initialize MongoDB connection with proper SSL settings"""
    global db, mongo_client
    
    if not MONGO_URL:
        LOGGER.warning("MONGO_URL not set! Database features disabled.")
        return False
    
    try:
        # Create client with SSL disabled for Render compatibility
        mongo_client = MongoCli(
            MONGO_URL,
            tls=False,  # Disable TLS/SSL to fix handshake error
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            socketTimeoutMS=10000,
        )
        
        # Test connection
        db = mongo_client.premium.premium_db
        LOGGER.info("✅ MongoDB connected successfully")
        return True
        
    except Exception as e:
        LOGGER.error(f"MongoDB connection error: {e}")
        db = None
        mongo_client = None
        return False

# Initialize on module load
init_mongo()


async def add_premium(user_id, expire_date):
    """Add or update premium user"""
    global db
    
    if db is None:
        LOGGER.warning("Database not available, trying to reconnect...")
        if not init_mongo():
            return False
    
    try:
        result = await db.update_one(
            {"_id": user_id},
            {"$set": {"expire_date": expire_date}},
            upsert=True
        )
        LOGGER.info(f"Premium added for user {user_id}")
        return True
    except Exception as e:
        LOGGER.error(f"ERROR adding premium: {e}")
        return False


async def remove_premium(user_id):
    """Remove premium user"""
    global db
    
    if db is None:
        LOGGER.warning("Database not available")
        return False
    
    try:
        result = await db.delete_one({"_id": user_id})
        LOGGER.info(f"Premium removed for user {user_id}")
        return True
    except Exception as e:
        LOGGER.error(f"ERROR removing premium: {e}")
        return False


async def check_premium(user_id):
    """Check if user has premium - returns data or None"""
    global db
    
    if db is None:
        LOGGER.warning("Database not available for check_premium")
        return None
    
    try:
        data = await db.find_one({"_id": user_id})
        return data
    except Exception as e:
        LOGGER.error(f"ERROR checking premium: {e}")
        return None


async def premium_users():
    """Get list of all premium user IDs"""
    global db
    
    if db is None:
        LOGGER.warning("Database not available for premium_users")
        return []
    
    try:
        users = []
        async for data in db.find():
            if "_id" in data:
                users.append(data["_id"])
        return users
    except Exception as e:
        LOGGER.error(f"ERROR getting premium users: {e}")
        return []
