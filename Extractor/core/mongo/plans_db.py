"""
MongoDB Database Functions for Premium Management
Fixed: Added SSL parameters to fix connection issues on Render
"""
from motor.motor_asyncio import AsyncIOMotorClient as MongoCli
from config import MONGO_URL

# Fix: Add SSL parameters for Render deployment
# This fixes the SSL handshake error
def get_mongo_client():
    """Create MongoDB client with proper SSL settings for Render"""
    if not MONGO_URL:
        print("WARNING: MONGO_URL not set!")
        return None
    
    try:
        # Add SSL parameters to fix SSL handshake error
        client = MongoCli(
            MONGO_URL,
            tls=True,
            tlsAllowInvalidCertificates=True,
            serverSelectionTimeoutMS=10000,
            connectTimeoutMS=10000,
            socketTimeoutMS=30000,
        )
        return client
    except Exception as e:
        print(f"ERROR: Failed to create MongoDB client: {e}")
        return None

# Initialize client
mongo_client = get_mongo_client()

if mongo_client:
    try:
        db = mongo_client.premium.premium_db
        print("✅ MongoDB connected successfully")
    except Exception as e:
        print(f"ERROR: Failed to access database: {e}")
        db = None
else:
    db = None


async def add_premium(user_id, expire_date):
    """Add or update premium user"""
    if not db:
        print("WARNING: Database not available, cannot add premium")
        return False
    
    try:
        await db.update_one(
            {"_id": user_id},
            {"$set": {"expire_date": expire_date}},
            upsert=True
        )
        return True
    except Exception as e:
        print(f"ERROR adding premium: {e}")
        return False


async def remove_premium(user_id):
    """Remove premium user"""
    if not db:
        print("WARNING: Database not available, cannot remove premium")
        return False
    
    try:
        await db.delete_one({"_id": user_id})
        return True
    except Exception as e:
        print(f"ERROR removing premium: {e}")
        return False


async def check_premium(user_id):
    """Check if user has premium - returns data or None"""
    if not db:
        print("WARNING: Database not available, cannot check premium")
        return None
    
    try:
        data = await db.find_one({"_id": user_id})
        return data
    except Exception as e:
        print(f"ERROR checking premium: {e}")
        return None


async def premium_users():
    """Get list of all premium user IDs"""
    if not db:
        print("WARNING: Database not available, returning empty list")
        return []
    
    try:
        users = []
        async for data in db.find():
            if "_id" in data:
                users.append(data["_id"])
        return users
    except Exception as e:
        print(f"ERROR getting premium users: {e}")
        return []
