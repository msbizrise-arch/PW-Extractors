from config import CHANNEL_ID, SUDO_USERS, OWNER_ID
from Extractor.core import script
from pyrogram.errors import UserNotParticipant
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from Extractor.core.mongo.plans_db import premium_users


async def chk_user(user_id):
    """Check if user has premium access. Returns 0 if allowed, 1 if not."""
    users = await premium_users()
    if user_id in users:
        return 0
    if user_id in SUDO_USERS:
        return 0
    if user_id == OWNER_ID:
        return 0
    return 1


async def subscribe(client, message):
    """Check if user is subscribed to the channel. Returns 0 if ok, 1 if not."""
    if not CHANNEL_ID or CHANNEL_ID == 0:
        return 0
    try:
        user = await client.get_chat_member(CHANNEL_ID, message.from_user.id)
        if user.status in ["kicked", "left"]:
            raise UserNotParticipant
        return 0
    except UserNotParticipant:
        try:
            url = await client.export_chat_invite_link(CHANNEL_ID)
        except Exception:
            return 0
        await message.reply_photo(
            "https://graph.org/file/2eb3c7ed975b9f9dffaa5-9b991b04b9478b1026.jpg",
            caption=script.FORCE_MSG.format(message.from_user.mention),
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Join Channel", url=url)]]
            ),
        )
        return 1
    except Exception:
        return 0


async def get_seconds(time_string):
    """Convert time string like '30days' to seconds."""
    value = int("".join(filter(str.isdigit, time_string)))
    unit = "".join(filter(str.isalpha, time_string)).lower()
    if unit.startswith("day"):
        return value * 86400
    if unit.startswith("hour"):
        return value * 3600
    if unit.startswith("min"):
        return value * 60
    if unit.startswith("month"):
        return value * 86400 * 30
    if unit.startswith("year"):
        return value * 86400 * 365
    return 0
