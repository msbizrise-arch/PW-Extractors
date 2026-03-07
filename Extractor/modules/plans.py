"""
Premium Plans Module - COMPLETE FIXED
✅ Database errors handled gracefully - bot won't crash
✅ OWNER always has premium (unlimited)
✅ All admin commands properly filtered & validated
✅ Time parsing uses fixed get_seconds from func.py
✅ Premium expiry checks use Asia/Kolkata timezone consistently
✅ Callback handler show_plan properly handles MESSAGE_NOT_MODIFIED
"""
from datetime import timedelta
import pytz
import datetime
from Extractor import app
from config import ADMIN_IDS, PREMIUM_LOGS, OWNER_ID, SUDO_USERS
from Extractor.core.func import get_seconds, format_time
from Extractor.core.mongo.plans_db import (
    add_premium,
    remove_premium, 
    check_premium,
    premium_users,
    is_premium_user,
)
from pyrogram import filters
from pyrogram.types import Message, CallbackQuery
import logging

LOGGER = logging.getLogger(__name__)

# ====================== ADMIN FILTER ======================
# Admins = OWNER + SUDO_USERS + explicit ADMIN_IDS
def admin_filter(_, __, message: Message):
    """Filter: Only allow admin users to execute commands."""
    user_id = message.from_user.id if message.from_user else 0
    return user_id in ADMIN_IDS or user_id == OWNER_ID or user_id in SUDO_USERS

admin_filter = filters.create(admin_filter)

# ====================== ADD PREMIUM COMMAND ======================
@app.on_message(filters.command("add_premium") & admin_filter & filters.private)
async def add_premium_cmd(client, message: Message):
    """Add premium to user (Admin only)"""
    
    # Validate command arguments
    if len(message.command) != 3:
        await message.reply_text(
            "📌 **Usage:**\n"
            "`/add_premium <user_id> <time>`\n\n"
            "**Examples:**\n"
            "`/add_premium 123456789 30days`\n"
            "`/add_premium 123456789 1month`\n"            "`/add_premium 123456789 1year`\n\n"
            "**Time formats:** `1day`, `7days`, `1month`, `1year`, `30d`, `1y`"
        )
        return
    
    # Parse user_id
    try:
        user_id = int(message.command[1])
    except (ValueError, IndexError):
        await message.reply_text("❌ **Invalid user ID.** Use a numeric Telegram user ID.")
        return
    
    # Cannot add premium to self via command (OWNER already has it)
    if user_id == OWNER_ID:
        await message.reply_text("⚠️ OWNER already has unlimited premium access.")
        return
    
    # Parse time duration
    time_str = message.command[2]
    seconds = await get_seconds(time_str)
    
    if seconds <= 0:
        await message.reply_text(
            "❌ **Invalid time format.** Use formats like:\n"
            "`30days`, `1month`, `7d`, `1y`, `90days`"
        )
        return
    
    # Calculate expiry date (Asia/Kolkata timezone)
    tz = pytz.timezone("Asia/Kolkata")
    expire_date = datetime.datetime.now(tz) + timedelta(seconds=seconds)
    
    # Add to database
    try:
        result = await add_premium(user_id, expire_date)
    except Exception as e:
        LOGGER.error(f"add_premium database error: {e}")
        await message.reply_text("❌ **Database error.** Could not add premium.")
        return
    
    if result:
        # Get user mention for display
        try:
            user = await client.get_users(user_id)
            user_name = user.mention
        except Exception:
            user_name = f"User `{user_id}`"
        
        # Success message to admin
        await message.reply_text(            f"✅ **Premium Added Successfully!**\n\n"
            f"👤 **User:** {user_name}\n"
            f"⚡ **ID:** `{user_id}`\n"
            f"⏰ **Duration:** {time_str}\n"
            f"📅 **Expires:** {expire_date.strftime('%d-%m-%Y %I:%M %p IST')}\n\n"
            f"User has been notified."
        )
        
        # Notify the user
        try:
            await client.send_message(
                user_id,
                f"🎉 **Premium Activated!**\n\n"
                f"⏰ **Duration:** {time_str}\n"
                f"📅 **Expires:** {expire_date.strftime('%d-%m-%Y %I:%M %p IST')}\n\n"
                f"Send /start to use the bot with premium features!\n"
                f"💎 Enjoy unlimited batch extraction!"
            )
        except Exception as e:
            LOGGER.warning(f"Could not notify user {user_id}: {e}")
            
        # Log to premium logs channel if configured
        if PREMIUM_LOGS and PREMIUM_LOGS != 0:
            try:
                await client.send_message(
                    PREMIUM_LOGS,
                    f"🔔 **Premium Added**\n"
                    f"👤 Admin: {message.from_user.mention}\n"
                    f"👤 User: {user_name} (`{user_id}`)\n"
                    f"⏰ Duration: {time_str}\n"
                    f"📅 Expires: {expire_date.strftime('%d-%m-%Y %I:%M %p IST')}"
                )
            except Exception as e:
                LOGGER.warning(f"Premium log send failed: {e}")
    else:
        await message.reply_text("❌ **Failed to add premium.** Database error.")

# ====================== REMOVE PREMIUM COMMAND ======================
@app.on_message(filters.command("remove_premium") & admin_filter & filters.private)
async def remove_premium_cmd(client, message: Message):
    """Remove premium from user (Admin only)"""
    
    if len(message.command) != 2:
        await message.reply_text(
            "📌 **Usage:**\n"
            "`/remove_premium <user_id>`\n\n"
            "**Example:** `/remove_premium 123456789`"
        )
        return
        try:
        user_id = int(message.command[1])
    except (ValueError, IndexError):
        await message.reply_text("❌ **Invalid user ID.** Use a numeric Telegram user ID.")
        return
    
    # Cannot remove OWNER's premium
    if user_id == OWNER_ID:
        await message.reply_text("❌ **Cannot remove OWNER's premium!** OWNER has unlimited access.")
        return
    
    # Check if user has premium
    try:
        data = await check_premium(user_id)
    except Exception as e:
        LOGGER.error(f"check_premium error: {e}")
        await message.reply_text("❌ **Database error.** Could not check premium status.")
        return
    
    if data is None:
        await message.reply_text(f"❌ **User `{user_id}` has no active premium plan.**")
        return
    
    # Remove premium
    try:
        result = await remove_premium(user_id)
    except Exception as e:
        LOGGER.error(f"remove_premium database error: {e}")
        await message.reply_text("❌ **Database error.** Could not remove premium.")
        return
    
    if result:
        await message.reply_text(f"✅ **Premium removed for user `{user_id}`!**")
        
        # Notify user
        try:
            await client.send_message(
                user_id,
                "⚠️ **Premium Access Removed**\n\n"
                "Your premium plan has been deactivated.\n"
                "Contact admin to reactivate."
            )
        except Exception:
            pass
            
        # Log to premium logs
        if PREMIUM_LOGS and PREMIUM_LOGS != 0:
            try:
                await client.send_message(
                    PREMIUM_LOGS,                    f"🔕 **Premium Removed**\n"
                    f"👤 Admin: {message.from_user.mention}\n"
                    f"👤 User: `{user_id}`"
                )
            except Exception:
                pass
    else:
        await message.reply_text("❌ **Failed to remove premium.** Database error.")

# ====================== CHECK PREMIUM USERS COMMAND ======================
@app.on_message(filters.command("chk_premium") & admin_filter & filters.private)
async def chk_premium_cmd(client, message: Message):
    """List all premium users (Admin only)"""
    
    try:
        users = await premium_users()
    except Exception as e:
        LOGGER.error(f"premium_users database error: {e}")
        await message.reply_text("❌ **Database error.** Could not fetch premium users.")
        return
    
    if not users:
        await message.reply_text("📭 **No premium users found.**")
        return
    
    # Build formatted list
    text = f"**⚜️ Premium Users ({len(users)}):**\n\n"
    
    tz = pytz.timezone("Asia/Kolkata")
    
    for idx, uid in enumerate(users[:30], 1):  # Limit to 30 for readability
        try:
            data = await check_premium(uid)
            if data and "expire_date" in 
                expiry = data["expire_date"]
                # Handle timezone-aware datetime
                if hasattr(expiry, 'astimezone'):
                    expiry = expiry.astimezone(tz)
                
                # Calculate time left
                now = datetime.datetime.now(tz)
                time_left = expiry - now
                time_str = format_time(int(time_left.total_seconds()))
                
                text += f"`{idx}.` `{uid}` - ⏰ `{time_str}` left - 📅 `{expiry.strftime('%d-%m-%Y')}`\n"
            else:
                text += f"`{idx}.` `{uid}` - ❓ No expiry data\n"
        except Exception as e:
            LOGGER.warning(f"Error fetching data for user {uid}: {e}")
            text += f"`{idx}.` `{uid}` - ⚠️ Error\n"    
    if len(users) > 30:
        text += f"\n_... and {len(users) - 30} more users_"
    
    await message.reply_text(text)

# ====================== MY PLAN COMMAND (User Self-Check) ======================
@app.on_message(filters.command("myplan") & filters.private)
async def myplan_cmd(client, message: Message):
    """Check user's own premium plan"""
    user_id = message.from_user.id
    user_mention = message.from_user.mention
    
    # OWNER is always premium with unlimited access
    if user_id == OWNER_ID:
        await message.reply_text(
            f"⚜️ **Premium User Data:**\n\n"
            f"👤 **User:** {user_mention}\n"
            f"⚡ **ID:** `{user_id}`\n"
            f"⏰ **Time Left:** **UNLIMITED** ♾️\n"
            f"📅 **Expiry:** **Never (OWNER)**\n\n"
            f"✅ You have full access to all features!"
        )
        return
    
    # Check premium status
    try:
        is_premium = await is_premium_user(user_id)
        data = await check_premium(user_id)
    except Exception as e:
        LOGGER.error(f"myplan database error: {e}")
        await message.reply_text("⚠️ Could not check premium status. Try again later.")
        return
    
    if not is_premium or data is None or "expire_date" not in 
        await message.reply_text(
            f"👤 **User:** {user_mention}\n\n"
            f"❌ **No active premium plan.**\n\n"
            f"💎 **Get Premium:**\n"
            f"• Unlimited batch extraction\n"
            f"• Search ALL PW batches\n"
            f"• Priority support\n\n"
            f"📞 Contact @SmartBoy_ApnaMS to purchase!"
        )
        return
    
    # Calculate and display time left
    try:
        expiry = data.get("expire_date")
        tz = pytz.timezone("Asia/Kolkata")        now = datetime.datetime.now(tz)
        
        if hasattr(expiry, 'astimezone'):
            expiry = expiry.astimezone(tz)
        
        time_left = expiry - now
        total_seconds = int(time_left.total_seconds())
        
        if total_seconds <= 0:
            time_str = "Expired"
        else:
            time_str = format_time(total_seconds)
        
        await message.reply_text(
            f"⚜️ **Premium User Data:**\n\n"
            f"👤 **User:** {user_mention}\n"
            f"⚡ **ID:** `{user_id}`\n"
            f"⏰ **Time Left:** {time_str}\n"
            f"📅 **Expires:** {expiry.strftime('%d-%m-%Y %I:%M %p IST')}\n\n"
            f"✅ You have premium access!"
        )
    except Exception as e:
        LOGGER.error(f"myplan time calculation error: {e}")
        await message.reply_text(
            f"👤 **User:** {user_mention}\n\n"
            f"✅ You have premium access!\n"
            f"⚠️ Could not calculate exact expiry time."
        )

# ====================== CALLBACK: SHOW PLAN ======================
async def show_plan(client, query: CallbackQuery):
    """Show plan details from callback query (used by start.py)"""
    user_id = query.from_user.id
    user_mention = query.from_user.mention
    
    try:
        # OWNER is always premium
        if user_id == OWNER_ID:
            text = (
                f"⚜️ **Premium User Data:**\n\n"
                f"👤 **User:** {user_mention}\n"
                f"⚡ **ID:** `{user_id}`\n"
                f"⏰ **Time Left:** **UNLIMITED** ♾️\n"
                f"📅 **Expiry:** **Never (OWNER)**"
            )
        else:
            is_premium = await is_premium_user(user_id)
            data = await check_premium(user_id)
            
            if not is_premium or data is None or "expire_date" not in data:                text = (
                    f"👤 **User:** {user_mention}\n\n"
                    f"❌ **No active premium plan.**\n\n"
                    f"💎 Contact admin to get premium access!"
                )
            else:
                expiry = data.get("expire_date")
                tz = pytz.timezone("Asia/Kolkata")
                now = datetime.datetime.now(tz)
                
                if hasattr(expiry, 'astimezone'):
                    expiry = expiry.astimezone(tz)
                
                time_left = expiry - now
                total_seconds = int(time_left.total_seconds())
                time_str = format_time(total_seconds) if total_seconds > 0 else "Expired"
                
                text = (
                    f"⚜️ **Premium User Data:**\n\n"
                    f"👤 **User:** {user_mention}\n"
                    f"⚡ **ID:** `{user_id}`\n"
                    f"⏰ **Time Left:** {time_str}\n"
                    f"📅 **Expires:** {expiry.strftime('%d-%m-%Y %I:%M %p IST')}"
                )
        
        # Try to edit message, handle MESSAGE_NOT_MODIFIED
        try:
            await query.message.edit_text(text)
        except Exception as e:
            if "MESSAGE_NOT_MODIFIED" in str(e):
                LOGGER.debug(f"show_plan: message not modified for user {user_id}")
            else:
                LOGGER.error(f"show_plan edit error: {e}")
                await query.answer("Error displaying plan!", show_alert=True)
                
    except Exception as e:
        LOGGER.error(f"show_plan unexpected error: {e}", exc_info=True)
        await query.answer("Error checking plan!", show_alert=True)
