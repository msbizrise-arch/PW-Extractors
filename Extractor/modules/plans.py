"""
Premium Plans Module - COMPLETE FIXED
Fixed: Database errors, OWNER always premium
"""
from datetime import timedelta
import pytz
import datetime
from Extractor import app
from config import ADMIN_IDS, PREMIUM_LOGS, OWNER_ID
from Extractor.core.func import get_seconds
from Extractor.core.mongo.plans_db import (
    add_premium,
    remove_premium,
    check_premium,
    premium_users,
)
from pyrogram import filters
from pyrogram.types import Message
import logging

LOGGER = logging.getLogger(__name__)

# Admin filter
admin_filter = filters.user(ADMIN_IDS) if ADMIN_IDS else filters.user([OWNER_ID])


@app.on_message(filters.command("add_premium") & admin_filter)
async def add_premium_cmd(client, message: Message):
    """Add premium to user (Admin only)"""
    if len(message.command) != 3:
        await message.reply_text(
            "**📌 Usage:**\n"
            "`/add_premium <user_id> <time>`\n\n"
            "**Examples:**\n"
            "`/add_premium 123456789 30days`\n"
            "`/add_premium 123456789 1month`\n\n"
            "**Time formats:** `1day`, `7days`, `1month`, `1year`"
        )
        return
    
    try:
        user_id = int(message.command[1])
    except ValueError:
        await message.reply_text("❌ Invalid user ID")
        return
    
    time_str = message.command[2]
    seconds = await get_seconds(time_str)
    
    if seconds == 0:
        await message.reply_text("❌ Invalid time format. Use: `30days`, `1month`")
        return
    
    tz = pytz.timezone("Asia/Kolkata")
    expire_date = datetime.datetime.now(tz) + timedelta(seconds=seconds)
    
    result = await add_premium(user_id, expire_date)
    
    if result:
        try:
            user = await client.get_users(user_id)
            user_name = user.mention
        except:
            user_name = f"User {user_id}"
        
        await message.reply_text(
            f"✅ **Premium Added!**\n\n"
            f"👤 User: {user_name}\n"
            f"⚡ ID: `{user_id}`\n"
            f"⏰ Duration: {time_str}\n"
            f"📅 Expires: {expire_date.strftime('%d-%m-%Y %I:%M %p')}"
        )
        
        # Notify user
        try:
            await client.send_message(
                user_id,
                f"🎉 **Premium Activated!**\n\n"
                f"⏰ Duration: {time_str}\n"
                f"📅 Expires: {expire_date.strftime('%d-%m-%Y %I:%M %p')}\n\n"
                f"Send /start to use the bot!"
            )
        except:
            pass
    else:
        await message.reply_text("❌ Failed to add premium.")


@app.on_message(filters.command("remove_premium") & admin_filter)
async def remove_premium_cmd(client, message: Message):
    """Remove premium from user (Admin only)"""
    if len(message.command) != 2:
        await message.reply_text("**📌 Usage:** `/remove_premium <user_id>`")
        return
    
    try:
        user_id = int(message.command[1])
    except ValueError:
        await message.reply_text("❌ Invalid user ID")
        return
    
    # Cannot remove OWNER's premium
    if user_id == OWNER_ID:
        await message.reply_text("❌ Cannot remove OWNER's premium!")
        return
    
    data = await check_premium(user_id)
    if data is None:
        await message.reply_text("❌ User has no premium.")
        return
    
    result = await remove_premium(user_id)
    
    if result:
        await message.reply_text(f"✅ Premium removed for user `{user_id}`!")
        try:
            await client.send_message(user_id, "⚠️ **Your premium access has been removed.**")
        except:
            pass
    else:
        await message.reply_text("❌ Failed to remove premium.")


@app.on_message(filters.command("chk_premium") & admin_filter)
async def chk_premium_cmd(client, message: Message):
    """List all premium users (Admin only)"""
    users = await premium_users()
    
    if not users:
        await message.reply_text("📭 No premium users.")
        return
    
    text = f"**⚜️ Premium Users ({len(users)}):**\n\n"
    
    for uid in users[:20]:
        try:
            data = await check_premium(uid)
            if data and "expire_date" in data:
                tz = pytz.timezone("Asia/Kolkata")
                expiry = data["expire_date"]
                if hasattr(expiry, 'astimezone'):
                    expiry = expiry.astimezone(tz)
                text += f"• `{uid}` - {expiry.strftime('%d-%m-%Y')}\n"
            else:
                text += f"• `{uid}` - No expiry\n"
        except:
            text += f"• `{uid}` - Error\n"
    
    if len(users) > 20:
        text += f"\n... and {len(users) - 20} more"
    
    await message.reply_text(text)


@app.on_message(filters.command("myplan") & filters.private)
async def myplan_cmd(client, message: Message):
    """Check user's premium plan"""
    user_id = message.from_user.id
    user_mention = message.from_user.mention
    
    # OWNER is always premium
    if user_id == OWNER_ID:
        await message.reply_text(
            f"⚜️ **Premium User Data:**\n\n"
            f"👤 User: {user_mention}\n"
            f"⚡ ID: `{user_id}`\n"
            f"⏰ Time Left: **UNLIMITED**\n"
            f"📅 Expiry: **Never (OWNER)**\n\n"
            f"✅ You have full access!"
        )
        return
    
    data = await check_premium(user_id)
    
    if not data or "expire_date" not in data:
        await message.reply_text(
            f"👤 **User:** {user_mention}\n\n"
            f"❌ No active premium plan.\n\n"
            f"💎 Contact admin to get premium access!"
        )
        return
    
    try:
        expiry = data.get("expire_date")
        tz = pytz.timezone("Asia/Kolkata")
        now = datetime.datetime.now(tz)
        
        if hasattr(expiry, 'astimezone'):
            expiry = expiry.astimezone(tz)
        
        time_left = expiry - now
        days = time_left.days
        hours, _ = divmod(time_left.seconds, 3600)
        
        await message.reply_text(
            f"⚜️ **Premium User Data:**\n\n"
            f"👤 User: {user_mention}\n"
            f"⚡ ID: `{user_id}`\n"
            f"⏰ Time Left: {days}d {hours}h\n"
            f"📅 Expiry: {expiry.strftime('%d-%m-%Y %I:%M %p')}"
        )
    except Exception as e:
        LOGGER.error(f"Myplan error: {e}")
        await message.reply_text(
            f"👤 **User:** {user_mention}\n\n"
            f"✅ You have premium access!"
        )


async def show_plan(client, query):
    """Show plan from callback"""
    user_id = query.from_user.id
    user_mention = query.from_user.mention
    
    # OWNER is always premium
    if user_id == OWNER_ID:
        text = (
            f"⚜️ **Premium User Data:**\n\n"
            f"👤 User: {user_mention}\n"
            f"⚡ ID: `{user_id}`\n"
            f"⏰ Time Left: **UNLIMITED**\n"
            f"📅 Expiry: **Never (OWNER)**"
        )
    else:
        data = await check_premium(user_id)
        
        if not data or "expire_date" not in data:
            text = (
                f"👤 **User:** {user_mention}\n\n"
                f"❌ No active premium plan.\n\n"
                f"💎 Contact admin to get premium access!"
            )
        else:
            try:
                expiry = data.get("expire_date")
                tz = pytz.timezone("Asia/Kolkata")
                now = datetime.datetime.now(tz)
                
                if hasattr(expiry, 'astimezone'):
                    expiry = expiry.astimezone(tz)
                
                time_left = expiry - now
                days = time_left.days
                hours, _ = divmod(time_left.seconds, 3600)
                
                text = (
                    f"⚜️ **Premium User Data:**\n\n"
                    f"👤 User: {user_mention}\n"
                    f"⚡ ID: `{user_id}`\n"
                    f"⏰ Time Left: {days}d {hours}h\n"
                    f"📅 Expiry: {expiry.strftime('%d-%m-%Y %I:%M %p')}"
                )
            except:
                text = f"👤 **User:** {user_mention}\n\n✅ You have premium access!"
    
    try:
        await query.message.edit_text(text)
    except Exception as e:
        if "MESSAGE_NOT_MODIFIED" not in str(e):
            LOGGER.error(f"show_plan error: {e}")
