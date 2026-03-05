from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URL
import datetime
import pytz

# Initialize MongoDB client
mongo = AsyncIOMotorClient(MONGO_URL)
db = mongo.pw_extractor.premium_users

async def add_premium(user_id, expire_date):
    """Add or update premium user"""
    await db.update_one(
        {"_id": user_id},
        {"$set": {"expire_date": expire_date, "joined": datetime.datetime.now(pytz.utc)}},
        upsert=True
    )

async def remove_premium(user_id):
    """Remove premium user"""
    await db.delete_one({"_id": user_id})

async def check_premium(user_id):
    """Check if user has premium"""
    data = await db.find_one({"_id": user_id})
    if data and "expire_date" in data:
        # Check if expired
        now = datetime.datetime.now(pytz.utc)
        if data["expire_date"] < now:
            await remove_premium(user_id)
            return None
    return data

async def premium_users():
    """Get list of all premium user IDs"""
    users = []
    async for data in db.find():
        # Check if expired
        if "expire_date" in data:
            now = datetime.datetime.now(pytz.utc)
            if data["expire_date"] > now:
                users.append(data["_id"])
            else:
                await remove_premium(data["_id"])
        else:
            users.append(data["_id"])
    return users

async def get_premium_count():
    """Get total premium users count"""
    count = 0
    async for data in db.find():
        if "expire_date" in data:
            now = datetime.datetime.now(pytz.utc)
            if data["expire_date"] > now:
                count += 1
    return count
