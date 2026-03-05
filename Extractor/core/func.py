"""
Helper Functions Module
Fixed: Better error handling for MongoDB issues - bot won't crash if DB fails
"""
from config import CHANNEL_ID, SUDO_USERS, OWNER_ID
from Extractor.core.script import FORCE_MSG
from pyrogram.errors import UserNotParticipant
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from Extractor.core.mongo.plans_db import premium_users


async def chk_user(user_id):
    """
    Check if user has premium access.
    Returns 0 if allowed, 1 if not.
    """
    # Owner always allowed
    if user_id == OWNER_ID and OWNER_ID != 0:
        return 0
    
    # Sudo users always allowed
    if user_id in SUDO_USERS:
        return 0
    
    # Check premium in database
    try:
        users = await premium_users()
        if user_id in users:
            return 0
    except Exception as e:
        print(f"WARNING: chk_user database error: {e}")
        # If database fails, allow access (fail open for better UX)
        return 0
    
    return 1


async def subscribe(app, message):
    """
    Check if user is subscribed to the channel.
    Returns 0 if ok, 1 if not subscribed.
    """
    if not CHANNEL_ID or CHANNEL_ID == 0:
        return 0
    
    try:
        user = await app.get_chat_member(CHANNEL_ID, message.from_user.id)
        if user.status in ["kicked", "left"]:
            raise UserNotParticipant
        return 0
    except UserNotParticipant:
        try:
            url = await app.export_chat_invite_link(CHANNEL_ID)
        except Exception:
            url = "https://t.me/"
        
        try:
            await message.reply_photo(
                "https://graph.org/file/a5ad11e14714f9da64830-c5cf91c2ce7d6127ae.jpg",
                caption=FORCE_MSG.format(message.from_user.mention),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📢 Join Channel", url=url)],
                    [InlineKeyboardButton("🔄 Try Again", callback_data="check_sub")]
                ])
            )
        except Exception:
            # Fallback to text message
            await message.reply_text(
                FORCE_MSG.format(message.from_user.mention),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📢 Join Channel", url=url)],
                    [InlineKeyboardButton("🔄 Try Again", callback_data="check_sub")]
                ])
            )
        return 1
    except Exception as e:
        print(f"Subscribe check error: {e}")
        return 0


async def get_seconds(time_string):
    """
    Convert time string like '30days' to seconds.
    Returns 0 if invalid format.
    """
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
    except Exception:
        return 0
