"""
Start Module - COMPLETE FIXED
All buttons working, OWNER always has access
"""
import logging
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from Extractor import app
from Extractor.core.script import START_TXT, IMG, HELP_TXT, PREMIUM_TXT
from Extractor.core.func import subscribe
from SPdatabase import is_premium_user, OWNER_ID
from SPpw import user_data, AWAITING_PHONE, AWAITING_TOKEN, AWAITING_KEYWORD, AWAITING_NL_TOKEN, get_working_token

LOGGER = logging.getLogger(__name__)

# ====================== KEYBOARDS ======================
def start_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Physics Wallah 🚀", callback_data="pw_menu")],
        [InlineKeyboardButton("💎 My Plan", callback_data="myplan"),
         InlineKeyboardButton("❓ Help", callback_data="help")],
        [InlineKeyboardButton("📢 Updates Channel", url="https://t.me/SmartBoy_ApnaMS")]
    ])


def pw_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📱 Mobile + OTP", callback_data="pw_mobile")],
        [InlineKeyboardButton("🔑 Direct Token", callback_data="pw_token")],
        [InlineKeyboardButton("🔓 Without Login", callback_data="pw_nologin")],
        [InlineKeyboardButton("🔙 Back", callback_data="go_start")]
    ])


def back_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back", callback_data="go_start")]
    ])


def premium_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 View Plans", callback_data="plans")],
        [InlineKeyboardButton("🔙 Back", callback_data="go_start")]
    ])


# ====================== /start ======================
@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    """Start command"""
    try:
        if await subscribe(client, message):
            return
    except Exception as e:
        LOGGER.error(f"Subscribe check error: {e}")

    user_mention = message.from_user.mention if message.from_user else "User"

    try:
        await message.reply_photo(
            IMG[0],
            caption=START_TXT.format(user_mention),
            reply_markup=start_kb(),
        )
    except Exception as e:
        LOGGER.error(f"Start photo error: {e}")
        await message.reply_text(
            START_TXT.format(user_mention),
            reply_markup=start_kb(),
        )


# ====================== /help ======================
@app.on_message(filters.command("help") & filters.private)
async def help_cmd(client, message):
    """Help command"""
    await message.reply_text(HELP_TXT, reply_markup=back_kb())


# ====================== CALLBACKS ======================
@app.on_callback_query(filters.regex("^check_sub$"))
async def check_sub_cb(client, query):
    """Check subscription"""
    try:
        await query.answer()
        await query.message.delete()
        await client.send_message(query.from_user.id, "/start")
    except Exception as e:
        LOGGER.error(f"check_sub_cb error: {e}")


@app.on_callback_query(filters.regex("^pw_menu$"))
async def pw_menu_cb(client, query):
    """PW Menu - Check premium"""
    try:
        await query.answer()
        
        user_id = query.from_user.id
        
        # OWNER always has access
        if user_id == OWNER_ID:
            await query.message.edit_text(
                "**🔐 Choose Login Method:**\n\n"
                "📱 **Mobile + OTP** — Login with your PW number\n"
                "🔑 **Direct Token** — Paste your PW bearer token\n"
                "🔓 **Without Login** — Search batches directly",
                reply_markup=pw_menu_kb(),
            )
            return
        
        # Check premium
        is_premium = await is_premium_user(user_id)
        
        if not is_premium:
            await query.message.edit_text(
                "**💎 Premium Required!**\n\n"
                "You need premium access to use this feature.\n"
                "Contact admin to get premium!",
                reply_markup=premium_kb(),
            )
            return

        await query.message.edit_text(
            "**🔐 Choose Login Method:**\n\n"
            "📱 **Mobile + OTP** — Login with your PW number\n"
            "🔑 **Direct Token** — Paste your PW bearer token\n"
            "🔓 **Without Login** — Search batches directly",
            reply_markup=pw_menu_kb(),
        )
        
    except Exception as e:
        LOGGER.error(f"pw_menu_cb error: {e}")
        await query.answer("Error! Try /start", show_alert=True)


@app.on_callback_query(filters.regex("^go_start$"))
async def go_start_cb(client, query):
    """Back to start"""
    try:
        await query.answer()
        user_mention = query.from_user.mention if query.from_user else "User"

        try:
            await query.message.delete()
        except:
            pass

        try:
            await client.send_photo(
                query.from_user.id,
                IMG[0],
                caption=START_TXT.format(user_mention),
                reply_markup=start_kb(),
            )
        except:
            await client.send_message(
                query.from_user.id,
                START_TXT.format(user_mention),
                reply_markup=start_kb(),
            )
    except Exception as e:
        LOGGER.error(f"go_start_cb error: {e}")


@app.on_callback_query(filters.regex("^help$"))
async def help_cb(client, query):
    """Help callback"""
    try:
        await query.answer()
        await query.message.edit_text(HELP_TXT, reply_markup=back_kb())
    except Exception as e:
        LOGGER.error(f"help_cb error: {e}")


@app.on_callback_query(filters.regex("^pw_mobile$"))
async def pw_mobile_cb(client, query):
    """Mobile OTP flow"""
    try:
        await query.answer()
        await query.message.delete()
        
        chat_id = query.from_user.id
        await client.send_message(
            chat_id,
            "**📱 Send your mobile number (without +91)**\n"
            "Example: `9876543210`\n\n"
            "Send /cancel to abort."
        )
        user_data[chat_id] = {"state": AWAITING_PHONE}
        
    except Exception as e:
        LOGGER.error(f"pw_mobile_cb error: {e}")


@app.on_callback_query(filters.regex("^pw_token$"))
async def pw_token_cb(client, query):
    """Token flow"""
    try:
        await query.answer()
        await query.message.delete()
        
        chat_id = query.from_user.id
        await client.send_message(
            chat_id,
            "**🔑 Send your PW Bearer Token**\n\n"
            "You can find this in:\n"
            "- Browser DevTools → Network tab\n"
            "- PW App (intercept traffic)\n\n"
            "Send /cancel to abort."
        )
        user_data[chat_id] = {"state": AWAITING_TOKEN}
        
    except Exception as e:
        LOGGER.error(f"pw_token_cb error: {e}")


@app.on_callback_query(filters.regex("^pw_nologin$"))
async def pw_nologin_cb(client, query):
    """Without login flow"""
    try:
        await query.answer()
        await query.message.delete()
        
        chat_id = query.from_user.id
        token = get_working_token()

        if not token:
            user_data[chat_id] = {"state": AWAITING_NL_TOKEN}
            await client.send_message(
                chat_id,
                "**🔓 Without Login — PW Batch Access**\n\n"
                "Please send a **working PW Bearer Token** to access batches.\n\n"
                "Send /cancel to abort."
            )
        else:
            user_data[chat_id] = {"state": AWAITING_KEYWORD, "nl_token": token}
            await client.send_message(
                chat_id,
                "**🔓 Without Login — PW Batch Search**\n\n"
                "Type a **batch keyword** to search:\n"
                "Examples: `Yakeen`, `Arjuna`, `Lakshya`, `Prayas`\n\n"
                "Send /cancel to abort."
            )
            
    except Exception as e:
        LOGGER.error(f"pw_nologin_cb error: {e}")


@app.on_callback_query(filters.regex("^plans$"))
async def plans_cb(client, query):
    """Show plans"""
    try:
        await query.answer()
        await query.message.edit_text(PREMIUM_TXT, reply_markup=back_kb())
    except Exception as e:
        LOGGER.error(f"plans_cb error: {e}")


@app.on_callback_query(filters.regex("^myplan$"))
async def myplan_cb(client, query):
    """My plan callback"""
    try:
        await query.answer()
        from SPplans import show_plan
        await show_plan(client, query)
    except Exception as e:
        LOGGER.error(f"myplan_cb error: {e}")
