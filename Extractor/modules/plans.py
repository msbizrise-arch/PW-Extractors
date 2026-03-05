from datetime import timedelta
import pytz
import datetime
from Extractor import app
from config import ADMIN_IDS, PREMIUM_LOGS
from Extractor.core.func import get_seconds
from Extractor.core.mongo.plans_db import (
    add_premium,
    remove_premium,
    check_premium,
    premium_users,
)
from pyrogram import filters
from pyrogram.types import Message


# Build admin filter (handle empty list)
admin_filter = filters.user(ADMIN_IDS) if ADMIN_IDS else filters.user([0])


@app.on_message(filters.command("add_premium") & admin_filter)
async def add_premium_cmd(client, message: Message):
    if len(message.command) != 3:
        await message.reply_text(
            "**Usage:** /add_premium <user_id> <time>\n"
            "**Example:** /add_premium 123456789 30days\n"
            "**Time formats:** 1day, 7days, 1month, 1year, 2hours"
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
            "❌ Invalid time format. Use like: 30days, 1month, 1year"
        )
        return

    tz = pytz.timezone("Asia/Kolkata")
    now = datetime.datetime.now(tz)
    expire_date = now + timedelta(seconds=seconds)

    await add_premium(user_id, expire_date)

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
            f"📅 Expires: {expire_date.strftime('%d-%m-%Y %I:%M %p IST')}",
        )
    except Exception:
        pass

    # Log to premium logs channel
    if PREMIUM_LOGS:
        try:
            await client.send_message(
                PREMIUM_LOGS,
                f"**Premium Added**\n"
                f"User: {user_name}\n"
                f"ID: `{user_id}`\n"
                f"Duration: {time_str}\n"
                f"By: {message.from_user.mention}",
            )
        except Exception:
            pass


@app.on_message(filters.command("remove_premium") & admin_filter)
async def remove_premium_cmd(client, message: Message):
    if len(message.command) != 2:
        await message.reply_text("**Usage:** /remove_premium <user_id>")
        return

    try:
        user_id = int(message.command[1])
    except ValueError:
        await message.reply_text("❌ Invalid user ID - must be a number")
        return

    data = await check_premium(user_id)
    if data:
        await remove_premium(user_id)
        try:
            user = await client.get_users(user_id)
            user_name = user.mention
        except Exception:
            user_name = f"User {user_id}"

        await message.reply_text(f"✅ Premium removed for {user_name}!")

        try:
            await client.send_message(
                user_id,
                f"Hey {user_name},\n\n"
                f"Your premium access has been removed.\n"
                f"Thank you for using our service!",
            )
        except Exception:
            pass
    else:
        await message.reply_text("❌ No premium data found for this user!")


@app.on_message(filters.command("chk_premium") & admin_filter)
async def chk_premium_cmd(client, message: Message):
    """Check all premium users."""
    users = await premium_users()
    if not users:
        await message.reply_text("No premium users found.")
        return

    text = "**⚜️ Premium Users:**\n\n"
    for uid in users:
        data = await check_premium(uid)
        if data and "expire_date" in data:
            tz = pytz.timezone("Asia/Kolkata")
            expiry = data["expire_date"].astimezone(tz)
            text += f"• `{uid}` - {expiry.strftime('%d-%m-%Y %I:%M %p')}\n"
        else:
            text += f"• `{uid}` - No expiry set\n"

    await message.reply_text(text)


@app.on_message(filters.command("myplan") & filters.private)
async def myplan_cmd(client, message: Message):
    user_id = message.from_user.id
    user_mention = message.from_user.mention
    data = await check_premium(user_id)

    if not data or "expire_date" not in data:
        await message.reply_text(
            f"Hey {user_mention},\n\n"
            f"You do not have any active premium plan.\n"
            f"Contact admin to get premium access!"
        )
        return

    expiry = data["expire_date"]
    tz = pytz.timezone("Asia/Kolkata")
    expiry_ist = expiry.astimezone(tz)
    now_ist = datetime.datetime.now(tz)
    time_left = expiry_ist - now_ist

    if time_left.total_seconds() <= 0:
        await message.reply_text(
            f"Hey {user_mention},\n\nYour premium has expired!"
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
        f"📅 Expiry: {expiry_ist.strftime('%d-%m-%Y %I:%M:%S %p IST')}"
    )


async def show_plan(client, query):
    """Called from callback query for 'myplan' button."""
    message = query.message
    user_id = query.from_user.id
    user_mention = query.from_user.mention
    data = await check_premium(user_id)

    if not data or "expire_date" not in data:
        await message.edit_text(
            f"Hey {user_mention},\n\n"
            f"You do not have any active premium plan.\n"
            f"Contact admin to get premium access!"
        )
        return

    expiry = data["expire_date"]
    tz = pytz.timezone("Asia/Kolkata")
    expiry_ist = expiry.astimezone(tz)
    now_ist = datetime.datetime.now(tz)
    time_left = expiry_ist - now_ist

    if time_left.total_seconds() <= 0:
        await message.edit_text(
            f"Hey {user_mention},\n\nYour premium has expired!"
        )
        await remove_premium(user_id)
        return

    days = time_left.days
    hours, remainder = divmod(time_left.seconds, 3600)
    minutes, _ = divmod(remainder, 60)

    await message.edit_text(
        f"⚜️ **Premium User Data:**\n\n"
        f"👤 User: {user_mention}\n"
        f"⚡ User ID: `{user_id}`\n"
        f"⏰ Time Left: {days}d {hours}h {minutes}m\n"
        f"📅 Expiry: {expiry_ist.strftime('%d-%m-%Y %I:%M:%S %p IST')}"
    )
