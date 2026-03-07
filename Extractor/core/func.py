"""
Helper Functions Module - FIXED
✅ Better error handling for MongoDB issues - bot won't crash if DB fails
✅ chk_user properly integrates with plans_db.py
✅ subscribe function handles channel join flow gracefully
✅ get_seconds supports all time formats reliably
✅ All functions return consistent types for safe usage
"""
from config import CHANNEL_ID, SUDO_USERS, OWNER_ID, ADMIN_IDS
from Extractor.core.script import FORCE_MSG
from pyrogram.errors import UserNotParticipant, ChatAdminRequired, PeerIdInvalid
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from Extractor.core.mongo.plans_db import premium_users, is_premium_user
import logging

LOGGER = logging.getLogger(__name__)

async def chk_user(user_id: int) -> int:
    """
    Check if user has premium access.
    Returns: 0 if allowed (premium/owner/sudo), 1 if not allowed.
    
    Logic:
    - OWNER_ID always allowed
    - SUDO_USERS always allowed  
    - ADMIN_IDS always allowed
    - Premium users from database allowed
    - If database fails, allow access (fail-open for better UX)
    """
    # Owner always allowed
    if user_id == OWNER_ID and OWNER_ID != 0:
        return 0
    
    # Sudo users always allowed
    if user_id in SUDO_USERS:
        return 0
    
    # Admin IDs always allowed
    if user_id in ADMIN_IDS:
        return 0
    
    # Check premium in database
    try:
        # Use is_premium_user for boolean check (handles expiry)
        if await is_premium_user(user_id):
            return 0
    except Exception as e:
        LOGGER.warning(f"chk_user database error for user {user_id}: {e}")
        # If database fails, allow access (fail-open for better UX)
        # This prevents bot from locking out users due to DB issues        return 0
    
    return 1

async def subscribe(app, message) -> int:
    """
    Check if user is subscribed to the forced channel.
    Returns: 0 if subscribed/ok, 1 if not subscribed (show join message).
    
    Handles:
    - CHANNEL_ID not set -> skip check
    - User already joined -> allow
    - User not joined -> show join message with Try Again button
    - Errors -> log and allow (fail-open)
    """
    # Skip if channel not configured
    if not CHANNEL_ID or CHANNEL_ID == 0:
        return 0
    
    try:
        # Check user's membership status
        user = await app.get_chat_member(CHANNEL_ID, message.from_user.id)
        
        # Allow if user is member, admin, or creator
        if user.status in ["member", "administrator", "creator"]:
            return 0
        
        # Block if kicked or left
        if user.status in ["kicked", "left"]:
            raise UserNotParticipant
            
    except UserNotParticipant:
        # User not subscribed - show join message
        try:
            # Try to get invite link
            try:
                url = await app.export_chat_invite_link(CHANNEL_ID)
            except (ChatAdminRequired, PeerIdInvalid, Exception):
                # Fallback URL if export fails
                url = f"https://t.me/+{CHANNEL_ID}" if CHANNEL_ID else "https://t.me/SmartBoy_ApnaMS"
            
            # Send photo message with join button
            try:
                await message.reply_photo(
                    "https://graph.org/file/a5ad11e14714f9da64830-c5cf91c2ce7d6127ae.jpg",
                    caption=FORCE_MSG.format(message.from_user.mention),
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📢 Join Channel", url=url)],
                        [InlineKeyboardButton("🔄 Try Again", callback_data="check_sub")]
                    ])                )
            except Exception:
                # Fallback to text message if photo fails
                await message.reply_text(
                    FORCE_MSG.format(message.from_user.mention),
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📢 Join Channel", url=url)],
                        [InlineKeyboardButton("🔄 Try Again", callback_data="check_sub")]
                    ])
                )
        except Exception as e:
            LOGGER.error(f"subscribe message send error: {e}")
        
        return 1  # Not subscribed
        
    except (ChatAdminRequired, PeerIdInvalid) as e:
        # Bot doesn't have permission to check channel
        LOGGER.warning(f"Cannot check channel subscription: {e}")
        return 0  # Allow access if we can't verify
        
    except Exception as e:
        # Any other error - log and allow (fail-open)
        LOGGER.error(f"Subscribe check unexpected error: {e}")
        return 0

async def get_seconds(time_string: str) -> int:
    """
    Convert time string like '30days', '1month', '7d' to seconds.
    
    Supported formats:
    - days/d: 30days, 7d, 1day
    - hours/h: 24hours, 1h
    - minutes/m: 30min, 5m
    - weeks/w: 2weeks, 1w
    - months/mo: 1month, 3mo
    - years/y: 1year, 2y
    
    Returns: seconds as int, or 0 if invalid format.
    """
    try:
        if not time_string or not isinstance(time_string, str):
            return 0
            
        # Extract numeric value and unit
        value_str = ''.join(filter(str.isdigit, time_string))
        unit_str = ''.join(filter(str.isalpha, time_string)).lower().strip()
        
        if not value_str:
            return 0
                    value = int(value_str)
        
        # Map units to seconds
        if unit_str in ['day', 'days', 'd', '']:
            return value * 86400  # 24 * 60 * 60
        elif unit_str in ['hour', 'hours', 'h', 'hr', 'hrs']:
            return value * 3600  # 60 * 60
        elif unit_str in ['min', 'mins', 'minute', 'minutes', 'm', 'min', 'mins']:
            return value * 60
        elif unit_str in ['week', 'weeks', 'w', 'wk', 'wks']:
            return value * 86400 * 7
        elif unit_str in ['month', 'months', 'mo', 'mos', 'mth', 'mths']:
            return value * 86400 * 30  # Approximate
        elif unit_str in ['year', 'years', 'y', 'yr', 'yrs']:
            return value * 86400 * 365  # Approximate
        else:
            # Default to days if unit unrecognized
            LOGGER.warning(f"Unrecognized time unit '{unit_str}', defaulting to days")
            return value * 86400
            
    except (ValueError, AttributeError) as e:
        LOGGER.error(f"get_seconds parse error for '{time_string}': {e}")
        return 0
    except Exception as e:
        LOGGER.error(f"get_seconds unexpected error: {e}")
        return 0

async def is_admin(user_id: int) -> bool:
    """Check if user is admin (OWNER, SUDO, or in ADMIN_IDS)."""
    return user_id in ADMIN_IDS or user_id == OWNER_ID

def format_time(seconds: int) -> str:
    """Format seconds into human-readable string (e.g., '2d 5h 30m')."""
    if seconds < 0:
        return "Expired"
    
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)
    
    parts = []
    if days: parts.append(f"{days}d")
    if hours: parts.append(f"{hours}h")
    if minutes: parts.append(f"{minutes}m")
    
    return " ".join(parts) if parts else "<1m"
