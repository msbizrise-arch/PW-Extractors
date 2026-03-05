from motor.motor_asyncio import AsyncIOMotorClient as MongoCli
from config import MONGO_URL

# Fix: Render + Python 3.12 → SSL: TLSV1_ALERT_INTERNAL_ERROR with MongoDB Atlas
mongo = MongoCli(
    MONGO_URL,
    tls=True,
    tlsAllowInvalidCertificates=True,
    serverSelectionTimeoutMS=30000,
    connectTimeoutMS=30000,
    socketTimeoutMS=30000,
)
db = mongo.premium.premium_db

async def add_premium(user_id, expire_date):
    await db.update_one({"_id": user_id}, {"$set": {"expire_date": expire_date}}, upsert=True)

async def remove_premium(user_id):
    await db.delete_one({"_id": user_id})

async def check_premium(user_id):
    return await db.find_one({"_id": user_id})

async def premium_users():
    return [data["_id"] async for data in db.find()]
