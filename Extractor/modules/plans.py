import datetime
import pytz
from Extractor import app
from config import SUDO_USERS, OWNER_ID, PREMIUM_LOGS
from Extractor.core.func import get_seconds
from Extractor.core.mongo.plans_db import (
    add_premium, remove_premium, check_premium, 
    premium_users, get_premium_count
)
from pyrogram import filters
from pyrogram.types import Message

# ====================== USER COMMANDS ======================

@app.on_message(filters.command("myplan"))
async def myplan_cmd(client, message: Message):
    """Check user's premium plan"""
    user_id = message.from_user.id
    user_mention = message.from_user.mention
    
    data = await check_premium(user_id)
    
    if not data:
        await message.reply_text(
            f"**👤 User:** {user_mention}\n"
            f"**🆔 ID:** `{user_id}`\n\n"
            f"❌ **You don't have an active premium plan!**\n\n"
            f"💎 Purchase premium to unlock unlimited extractions.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💎 View Plans", callback_data="plans")]
            ])
        )
        return
    
    expiry = data["expire_date"]
    tz = pytz.timezone("Asia/Kolkata")
    expiry_ist = expiry.astimezone(tz)
    expiry_str = expiry_ist.strftime("%d-%m-%Y\n⏱️ **Time:** %I:%M:%S %p")
    
    now_ist = datetime.datetime.now(tz)
    time_left = expiry_ist - now_ist
    
    if time_left.total_seconds() <= 0:
        await message.reply_text(
            f"**👤 User:** {user_mention}\n\n"
            f"❌ **Your premium has expired!**\n\n"
            f"💎 Renew your plan to continue using premium features."
        )
        await remove_premium(user_id)
        return
    
    days = time_left.days
    hours, remainder = divmod(time_left.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    time_left_str = f"{days} days, {hours} hours, {minutes} minutes"
    
    await message.reply_text(
        f"**⚜️ Premium User Data**\n\n"
        f"👤 **User:** {user_mention}\n"
        f"🆔 **ID:** `{user_id}`\n"
        f"⏰ **Time Left:** {time_left_str}\n"
        f"⌛️ **Expiry Date:** {expiry_str}\n\n"
        f"✅ **Status:** Active"
    )


@app.on_callback_query(filters.regex("myplan"))
async def myplan_cb(client, query):
    """Callback for myplan button"""
    await myplan_cmd(client, query.message)


# ====================== ADMIN COMMANDS ======================

@app.on_message(filters.command("addpremium") & filters.user(SUDO_USERS))
async def add_premium_cmd(client, message: Message):
    """Add premium to a user (Admin only)"""
    if len(message.command) < 3:
        await message.reply_text(
            "**📌 Usage:**\n"
            "`/addpremium user_id duration`\n\n"
            "**Examples:**\n"
            "`/addpremium 123456789 7days`\n"
            "`/addpremium 123456789 1month`\n"
            "`/addpremium 123456789 1year`"
        )
        return
    
    try:
        user_id = int(message.command[1])
        time_input = message.command[2].lower()
    except ValueError:
        await message.reply_text("❌ **Invalid user ID!** Must be a number.")
        return
    
    # Calculate expiry
    seconds = await get_seconds(time_input)
    if seconds == 0:
        await message.reply_text(
            "❌ **Invalid time format!**\n\n"
            "Use: `1day`, `7days`, `1month`, `1year`"
        )
        return
    
    tz = pytz.timezone("Asia/Kolkata")
    expiry_date = datetime.datetime.now(tz) + datetime.timedelta(seconds=seconds)
    
    # Add to database
    await add_premium(user_id, expiry_date)
    
    # Get user info
    try:
        user = await client.get_users(user_id)
        user_mention = user.mention
    except:
        user_mention = f"User {user_id}"
    
    # Notify user
    try:
        await client.send_message(
            chat_id=user_id,
            text=(
                f"**🎉 Congratulations {user_mention}!**\n\n"
                f"✅ **Premium Activated!**\n\n"
                f"⏰ **Duration:** {time_input}\n"
                f"⌛️ **Expires:** {expiry_date.strftime('%d-%m-%Y %I:%M %p')}\n\n"
                f"💎 Enjoy unlimited extractions!"
            )
        )
    except Exception as e:
        print(f"Could not notify user: {e}")
    
    # Log to premium logs channel
    if PREMIUM_LOGS:
        try:
            await client.send_message(
                chat_id=PREMIUM_LOGS,
                text=(
                    f"**💎 New Premium Added**\n\n"
                    f"👤 **User:** {user_mention}\n"
                    f"🆔 **ID:** `{user_id}`\n"
                    f"⏰ **Duration:** {time_input}\n"
                    f"⌛️ **Expires:** {expiry_date.strftime('%d-%m-%Y %I:%M %p')}\n\n"
                    f"👮 **Added by:** {message.from_user.mention}"
                )
            )
        except:
            pass
    
    await message.reply_text(
        f"**✅ Premium Added Successfully!**\n\n"
        f"👤 **User:** {user_mention}\n"
        f"🆔 **ID:** `{user_id}`\n"
        f"⏰ **Duration:** {time_input}\n"
        f"⌛️ **Expires:** {expiry_date.strftime('%d-%m-%Y %I:%M %p')}"
    )


@app.on_message(filters.command("removepremium") & filters.user(SUDO_USERS))
async def remove_premium_cmd(client, message: Message):
    """Remove premium from a user (Admin only)"""
    if len(message.command) != 2:
        await message.reply_text("**📌 Usage:** `/removepremium user_id`")
        return
    
    try:
        user_id = int(message.command[1])
    except ValueError:
        await message.reply_text("❌ **Invalid user ID!** Must be a number.")
        return
    
    # Check if user has premium
    data = await check_premium(user_id)
    if not data:
        await message.reply_text("❌ **User doesn't have premium!**")
        return
    
    # Remove from database
    await remove_premium(user_id)
    
    # Get user info
    try:
        user = await client.get_users(user_id)
        user_mention = user.mention
    except:
        user_mention = f"User {user_id}"
    
    # Notify user
    try:
        await client.send_message(
            chat_id=user_id,
            text=(
                f"**⚠️ Premium Removed**\n\n"
                f"Hey {user_mention},\n\n"
                f"Your premium access has been removed.\n"
                f"Contact admin if you think this is a mistake."
            )
        )
    except:
        pass
    
    await message.reply_text(
        f"**✅ Premium Removed!**\n\n"
        f"👤 **User:** {user_mention}\n"
        f"🆔 **ID:** `{user_id}`"
    )


@app.on_message(filters.command("checkpremium") & filters.user(SUDO_USERS))
async def check_premium_cmd(client, message: Message):
    """Check a user's premium status (Admin only)"""
    if len(message.command) != 2:
        await message.reply_text("**📌 Usage:** `/checkpremium user_id`")
        return
    
    try:
        user_id = int(message.command[1])
    except ValueError:
        await message.reply_text("❌ **Invalid user ID!** Must be a number.")
        return
    
    # Get user info
    try:
        user = await client.get_users(user_id)
        user_mention = user.mention
    except:
        user_mention = f"User {user_id}"
    
    # Check premium
    data = await check_premium(user_id)
    
    if not data:
        await message.reply_text(
            f"**👤 User:** {user_mention}\n"
            f"🆔 **ID:** `{user_id}`\n\n"
            f"❌ **No premium data found!**"
        )
        return
    
    expiry = data["expire_date"]
    tz = pytz.timezone("Asia/Kolkata")
    expiry_ist = expiry.astimezone(tz)
    expiry_str = expiry_ist.strftime("%d-%m-%Y %I:%M %p")
    
    now_ist = datetime.datetime.now(tz)
    time_left = expiry_ist - now_ist
    
    if time_left.total_seconds() <= 0:
        status = "❌ Expired"
        await remove_premium(user_id)
    else:
        status = "✅ Active"
    
    await message.reply_text(
        f"**⚜️ Premium Status**\n\n"
        f"👤 **User:** {user_mention}\n"
        f"🆔 **ID:** `{user_id}`\n"
        f"⌛️ **Expiry:** {expiry_str}\n"
        f"📊 **Status:** {status}"
    )


@app.on_message(filters.command("premiumusers") & filters.user(SUDO_USERS))
async def premium_users_cmd(client, message: Message):
    """List all premium users (Admin only)"""
    users = await premium_users()
    count = len(users)
    
    if count == 0:
        await message.reply_text("📊 **No premium users found!**")
        return
    
    text = f"**💎 Premium Users ({count})**\n\n"
    
    for i, user_id in enumerate(users[:50], 1):  # Limit to 50
        try:
            user = await client.get_users(user_id)
            text += f"{i}. {user.mention} (`{user_id}`)\n"
        except:
            text += f"{i}. User ID: `{user_id}`\n"
    
    if count > 50:
        text += f"\n... and {count - 50} more users"
    
    await message.reply_text(text)


@app.on_message(filters.command("stats") & filters.user(SUDO_USERS))
async def stats_cmd(client, message: Message):
    """Show bot statistics (Admin only)"""
    premium_count = await get_premium_count()
    
    await message.reply_text(
        f"**📊 Bot Statistics**\n\n"
        f"💎 **Premium Users:** {premium_count}\n"
        f"👮 **Sudo Users:** {len(SUDO_USERS)}\n"
        f"👑 **Owner ID:** `{OWNER_ID}`"
    )


# Import InlineKeyboardMarkup for buttons
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
