from config import CHANNEL_ID, SUDO_USERS
from Extractor.core.script import FORCE_MSG
from pyrogram.errors import UserNotParticipant
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from Extractor.core.mongo.plans_db import premium_users

async def chk_user(user_id):
    """Check if user is premium or sudo"""
    users = await premium_users()
    if user_id in users or user_id in SUDO_USERS:
        return 0  # Allowed
    return 1  # Not allowed

async def subscribe(app, message):
    """Check if user joined the required channel"""
    if not CHANNEL_ID or CHANNEL_ID == 0:
        return 0  # No channel set
    
    try:
        user = await app.get_chat_member(CHANNEL_ID, message.from_user.id)
        if user.status in ["kicked", "left"]:
            raise UserNotParticipant
        return 0  # User is member
    except UserNotParticipant:
        try:
            url = await app.export_chat_invite_link(CHANNEL_ID)
        except:
            url = "https://t.me/"
        
        await message.reply_photo(
            "https://graph.org/file/b7a933f423c153f866699.jpg",
            caption=FORCE_MSG.format(message.from_user.mention),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 Join Channel", url=url)],
                [InlineKeyboardButton("🔄 Try Again", callback_data="check_sub")]
            ])
        )
        return 1  # User not member
    except Exception as e:
        print(f"Subscribe check error: {e}")
        return 0  # Allow on error

async def get_seconds(time_string):
    """Convert time string to seconds"""
    try:
        value = int(''.join(filter(str.isdigit, time_string)))
        unit = ''.join(filter(str.isalpha, time_string)).lower()
        
        if unit.startswith('day') or unit.startswith('d'):
            return value * 86400
        elif unit.startswith('hour') or unit.startswith('h'):
            return value * 3600
        elif unit.startswith('min') or unit.startswith('m'):
            return value * 60
        elif unit.startswith('week') or unit.startswith('w'):
            return value * 86400 * 7
        elif unit.startswith('month') or unit.startswith('mo'):
            return value * 86400 * 30
        elif unit.startswith('year') or unit.startswith('y'):
            return value * 86400 * 365
        else:
            return value * 86400  # Default to days
    except:
        return 0
