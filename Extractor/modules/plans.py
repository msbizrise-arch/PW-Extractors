"""
Premium Plans Module - FIXED
Fixed: Database errors, MESSAGE_NOT_MODIFIED errors
"""
from datetime import timedelta
import pytz
import datetime
from Extractor import app
from msconfig import ADMIN_IDS, PREMIUM_LOGS, OWNER_ID, SUDO_USERS
from Extractor.core.func import get_seconds
from msplans_db import add_premium, remove_premium, check_premium, premium_users
from pyrogram import filters
from pyrogram.types import Message
import logging

LOGGER = logging.getLogger(__name__)

# Build admin filter
admin_filter = filters.user(ADMIN_IDS) if ADMIN_IDS else filters.user([OWNER_ID])


@app.on_message(filters.command("add_premium") & admin_filter)
async def add_premium_cmd(client, message: Message):
    """Add premium to a user (Admin only)"""
    if len(message.command) != 3:
        await message.reply_text(
            "**📌 Usage:**\n"
            "`/add_premium <user_id> <time>`\n\n"
            "**Examples:**\n"
            "`/add_premium 123456789 30days`\n"
            "`/add_premium 123456789 1month`\n"
            "`/add_premium 123456789 7days`\n\n"
            "**Time formats:** `1day`, `7days`, `1month`, `1year`, `2hours`"
        )
        return
    
    try:
        user_id = int(message.command[1])
    except ValueError:
        await message.reply_text("❌ Invalid user ID - must be a number")
        return
    
    time_str = message.command[2]
    seconds = await get_seconds(time_str)
    
    if seconds == 0:
        await message.reply_text(
            "❌ Invalid time format.\n"
            "Use like: `30days`, `1month`, `1year`, `2hours`"
        )
        return
    
    tz = pytz.timezone("Asia/Kolkata")
    now = datetime.datetime.now(tz)
    expire_date = now + timedelta(seconds=seconds)
    
    # Add premium
    result = await add_premium(user_id, expire_date)
    
    if not result:
        await message.reply_text(
            "❌ Failed to add premium.\n"
            "Database connection issue. Please check logs."
        )
        return
    
    try:
        user = await client.get_users(user_id)
        user_name = user.mention
    except Exception:
        user_name = f"User {user_id}"
    
    await message.reply_text(
        f"✅ **Premium Added!**\n\n"
        f"👤 User: {user_name}\n"
        f"⚡ User ID: `{user_id}`\n"
        f"⏰ Duration: {time_str}\n"
        f"📅 Expires: {expire_date.strftime('%d-%m-%Y %I:%M %p IST')}"
    )
    
    # Notify the user
    try:
        await client.send_message(
            user_id,
            f"🎉 **Congratulations!**\n\n"
            f"You have been granted premium access!\n"
            f"⏰ Duration: {time_str}\n"
            f"📅 Expires: {expire_date.strftime('%d-%m-%Y %I:%M %p IST')}\n\n"
            f"Send /start to use the bot!"
        )
    except Exception as e:
        LOGGER.error(f"Could not notify user: {e}")
    
    # Log to premium logs channel
    if PREMIUM_LOGS:
        try:
            await client.send_message(
                PREMIUM_LOGS,
                f"**💎 Premium Added**\n\n"
                f"👤 User: {user_name}\n"
                f"🆔 ID: `{user_id}`\n"
                f"⏰ Duration: {time_str}\n"
                f"👮 By: {message.from_user.mention}"
            )
        except Exception as e:
            LOGGER.error(f"Could not log to channel: {e}")


@app.on_message(filters.command("remove_premium") & admin_filter)
async def remove_premium_cmd(client, message: Message):
    """Remove premium from a user (Admin only)"""
    if len(message.command) != 2:
        await message.reply_text("**📌 Usage:** `/remove_premium <user_id>`")
        return
    
    try:
        user_id = int(message.command[1])
    except ValueError:
        await message.reply_text("❌ Invalid user ID - must be a number")
        return
    
    # Check if user has premium
    data = await check_premium(user_id)
    if data is None:
        await message.reply_text("❌ No premium data found for this user!")
        return
    
    # Remove premium
    result = await remove_premium(user_id)
    
    if not result:
        await message.reply_text("❌ Failed to remove premium.")
        return
    
    try:
        user = await client.get_users(user_id)
        user_name = user.mention
    except Exception:
        user_name = f"User {user_id}"
    
    await message.reply_text(f"✅ Premium removed for {user_name}!")
    
    try:
        await client.send_message(
            user_id,
            f"⚠️ **Premium Removed**\n\n"
            f"Hey {user_name},\n\n"
            f"Your premium access has been removed.\n"
            f"Contact admin if you think this is a mistake."
        )
    except Exception:
        pass


@app.on_message(filters.command("chk_premium") & admin_filter)
async def chk_premium_cmd(client, message: Message):
    """Check all premium users (Admin only)"""
    users = await premium_users()
    
    if not users:
        await message.reply_text("📭 No premium users found.")
        return
    
    text = f"**⚜️ Premium Users ({len(users)}):**\n\n"
    count = 0
    
    for uid in users[:20]:  # Limit to 20 users
        try:
            data = await check_premium(uid)
            if data is not None and "expire_date" in data:
                tz = pytz.timezone("Asia/Kolkata")
                expiry = data["expire_date"].astimezone(tz)
                text += f"• `{uid}` - {expiry.strftime('%d-%m-%Y')}\n"
                count += 1
            else:
                text += f"• `{uid}` - No expiry\n"
                count += 1
        except Exception as e:
            text += f"• `{uid}` - Error\n"
    
    if len(users) > 20:
        text += f"\n... and {len(users) - 20} more users"
    
    await message.reply_text(text)


@app.on_message(filters.command("myplan") & filters.private)
async def myplan_cmd(client, message: Message):
    """Check user's premium plan"""
    user_id = message.from_user.id
    user_mention = message.from_user.mention
    
    data = await check_premium(user_id)
    
    if data is None or "expire_date" not in data:
        await message.reply_text(
            f"👤 **User:** {user_mention}\n\n"
            f"❌ You do not have any active premium plan.\n\n"
            f"💎 Contact admin to get premium access!"
        )
        return
    
    try:
        expiry = data["expire_date"]
        tz = pytz.timezone("Asia/Kolkata")
        expiry_ist = expiry.astimezone(tz)
        now_ist = datetime.datetime.now(tz)
        time_left = expiry_ist - now_ist
        
        if time_left.total_seconds() <= 0:
            await message.reply_text(
                f"👤 **User:** {user_mention}\n\n"
                f"❌ Your premium has expired!\n\n"
                f"💎 Contact admin to renew."
            )
            await remove_premium(user_id)
            return
        
        days = time_left.days
        hours, remainder = divmod(time_left.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        
        await message.reply_text(
            f"⚜️ **Premium User Data:**\n\n"
            f"👤 User: {user_mention}\n"
            f"⚡ User ID: `{user_id}`\n"
            f"⏰ Time Left: {days}d {hours}h {minutes}m\n"
            f"📅 Expiry: {expiry_ist.strftime('%d-%m-%Y %I:%M %p IST')}"
        )
    except Exception as e:
        LOGGER.error(f"Myplan display error: {e}")
        await message.reply_text(
            f"👤 **User:** {user_mention}\n\n"
            f"✅ You have premium access!\n"
            f"(Error calculating expiry details)"
        )


async def show_plan(client, query):
    """Called from callback query for 'myplan' button."""
    message = query.message
    user_id = query.from_user.id
    user_mention = query.from_user.mention
    
    data = await check_premium(user_id)
    
    if data is None or "expire_date" not in data:
        # FIXED: Handle MESSAGE_NOT_MODIFIED error
        new_text = (
            f"👤 **User:** {user_mention}\n\n"
            f"❌ You do not have any active premium plan.\n\n"
            f"💎 Contact admin to get premium access!"
        )
        try:
            await message.edit_text(new_text)
        except Exception as e:
            if "MESSAGE_NOT_MODIFIED" in str(e):
                await query.answer("No premium plan active!")
            else:
                LOGGER.error(f"Show plan error: {e}")
        return
    
    try:
        expiry = data["expire_date"]
        tz = pytz.timezone("Asia/Kolkata")
        expiry_ist = expiry.astimezone(tz)
        now_ist = datetime.datetime.now(tz)
        time_left = expiry_ist - now_ist
        
        if time_left.total_seconds() <= 0:
            new_text = (
                f"👤 **User:** {user_mention}\n\n"
                f"❌ Your premium has expired!\n\n"
                f"💎 Contact admin to renew."
            )
            try:
                await message.edit_text(new_text)
            except Exception as e:
                if "MESSAGE_NOT_MODIFIED" in str(e):
                    await query.answer("Premium expired!")
            await remove_premium(user_id)
            return
        
        days = time_left.days
        hours, remainder = divmod(time_left.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        
        new_text = (
            f"⚜️ **Premium User Data:**\n\n"
            f"👤 User: {user_mention}\n"
            f"⚡ User ID: `{user_id}`\n"
            f"⏰ Time Left: {days}d {hours}h {minutes}m\n"
            f"📅 Expiry: {expiry_ist.strftime('%d-%m-%Y %I:%M %p IST')}"
        )
        try:
            await message.edit_text(new_text)
        except Exception as e:
            if "MESSAGE_NOT_MODIFIED" in str(e):
                await query.answer("Premium info displayed!")
            else:
                LOGGER.error(f"Show plan edit error: {e}")
                
    except Exception as e:
        LOGGER.error(f"Show plan display error: {e}")
        new_text = (
            f"👤 **User:** {user_mention}\n\n"
            f"✅ You have premium access!\n"
            f"(Error calculating expiry details)"
        )
        try:
            await message.edit_text(new_text)
        except:
            pass
