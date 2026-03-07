"""
Start Module - Handles /start command and callbacks
FINAL FIXED: No import errors, no message not modified
"""
import logging
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from Extractor import app
from Extractor.core.script import START_TXT, IMG, HELP_TXT, PREMIUM_TXT
from Extractor.core.func import subscribe, chk_user
from config import OWNER_ID

LOGGER = logging.getLogger(__name__)

# ====================== KEYBOARD LAYOUTS ======================
def get_start_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Physics Wallah 🚀", callback_data="pw_menu")],
        [InlineKeyboardButton("💎 My Plan", callback_data="myplan"),
         InlineKeyboardButton("❓ Help", callback_data="help")],
        [InlineKeyboardButton("📢 Updates Channel", url="https://t.me/SmartBoy_ApnaMS")]
    ])

def get_pw_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📱 Mobile + OTP", callback_data="pw_mobile")],
        [InlineKeyboardButton("🔑 Direct Token", callback_data="pw_token")],
        [InlineKeyboardButton("🔓 Without Login", callback_data="pw_nologin")],
        [InlineKeyboardButton("🔙 Back", callback_data="go_start")]
    ])

def get_back_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back", callback_data="go_start")]
    ])

def get_premium_required_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 View Plans", callback_data="plans")],
        [InlineKeyboardButton("🔙 Back", callback_data="go_start")]
    ])


# ====================== COMMANDS ======================
@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    try:
        if await subscribe(client, message):
            return
    except Exception as e:
        LOGGER.error(f"Subscribe error: {e}")

    user_mention = message.from_user.mention if message.from_user else "User"
    try:
        await message.reply_photo(
            IMG[0],
            caption=START_TXT.format(user_mention),
            reply_markup=get_start_keyboard(),
        )
    except Exception:
        await message.reply_text(
            START_TXT.format(user_mention),
            reply_markup=get_start_keyboard(),
        )


@app.on_message(filters.command("help") & filters.private)
async def help_cmd(client, message):
    await message.reply_text(HELP_TXT, reply_markup=get_back_keyboard())


# ====================== CALLBACK HANDLERS ======================
@app.on_callback_query(filters.regex("^check_sub$"))
async def check_sub_cb(client, query):
    await query.answer()
    await query.message.delete()
    await client.send_message(query.from_user.id, "/start")


@app.on_callback_query(filters.regex("^pw_menu$"))
async def pw_menu_cb(client, query):
    await query.answer()
    user_id = query.from_user.id

    menu_text = (
        "**🔐 Choose Login Method:**\n\n"
        "📱 **Mobile + OTP** — Login with your PW registered number\n"
        "🔑 **Direct Token** — Paste your PW bearer token\n"
        "🔓 **Without Login** — Search & extract batches directly"
    )

    # Owner direct access
    if user_id == OWNER_ID:
        # Check if message is different to avoid MESSAGE_NOT_MODIFIED
        if query.message.text != menu_text:
            await query.message.edit_text(menu_text, reply_markup=get_pw_menu_keyboard())
        return

    not_allowed = await chk_user(user_id)
    if not_allowed:
        await query.answer("You need premium access!", show_alert=True)
        premium_text = "**💎 Premium Required!**\n\nYou need to purchase a plan."
        if query.message.text != premium_text:
            await query.message.edit_text(premium_text, reply_markup=get_premium_required_keyboard())
        return

    if query.message.text != menu_text:
        await query.message.edit_text(menu_text, reply_markup=get_pw_menu_keyboard())


@app.on_callback_query(filters.regex("^go_start$"))
async def go_start_cb(client, query):
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
            reply_markup=get_start_keyboard(),
        )
    except:
        await client.send_message(
            query.from_user.id,
            START_TXT.format(user_mention),
            reply_markup=get_start_keyboard(),
        )


@app.on_callback_query(filters.regex("^help$"))
async def help_cb(client, query):
    await query.answer()
    if query.message.text != HELP_TXT:
        await query.message.edit_text(HELP_TXT, reply_markup=get_back_keyboard())


@app.on_callback_query(filters.regex("^pw_mobile$"))
async def pw_mobile_cb(client, query):
    await query.answer()
    try:
        await query.message.delete()
    except:
        pass

    chat_id = query.from_user.id
    from Extractor.modules.pw import user_data, AWAITING_PHONE
    user_data[chat_id] = {"state": AWAITING_PHONE}
    await client.send_message(
        chat_id,
        "**📱 Send your mobile number (without +91)**\n"
        "Example: `9876543210`\n\n"
        "Send /cancel to abort."
    )


@app.on_callback_query(filters.regex("^pw_token$"))
async def pw_token_cb(client, query):
    await query.answer()
    try:
        await query.message.delete()
    except:
        pass

    chat_id = query.from_user.id
    from Extractor.modules.pw import user_data, AWAITING_TOKEN
    user_data[chat_id] = {"state": AWAITING_TOKEN}
    await client.send_message(
        chat_id,
        "**🔑 Send your PW Bearer Token**\n\n"
        "Send /cancel to abort."
    )


@app.on_callback_query(filters.regex("^pw_nologin$"))
async def pw_nologin_cb(client, query):
    await query.answer()
    try:
        await query.message.delete()
    except:
        pass

    chat_id = query.from_user.id
    from Extractor.modules.pw import user_data, AWAITING_KEYWORD, _get_working_token
    
    token = _get_working_token()
    user_data[chat_id] = {"state": AWAITING_KEYWORD, "nl_token": token}
    
    msg = (
        "**🔓 Without Login — PW Batch Search**\n\n"
        "Type a **batch keyword** to search:\n\n"
        "**Popular Keywords:**\n"
        "• `Yakeen` (NEET)\n"
        "• `Arjuna` (JEE)\n"
        "• `Lakshya` (JEE/NEET)\n"
        "• `Prayas` (JEE)\n"
        "• `Udaan` (Class 11/12)\n"
        "• `NEET`\n"
        "• `JEE`\n\n"
        "Send /cancel to abort."
    )
    
    if not token:
        msg = (
            "⚠️ **Universal token not configured!**\n\n"
            "Without Login feature requires a working PW token.\n"
            "Contact admin to set PW_UNIVERSAL_TOKEN.\n\n"
            "For now, use:\n"
            "• 📱 Mobile + OTP\n"
            "• 🔑 Direct Token"
        )
    
    await client.send_message(chat_id, msg)


@app.on_callback_query(filters.regex("^plans$"))
async def plans_cb(client, query):
    await query.answer()
    if query.message.text != PREMIUM_TXT:
        await query.message.edit_text(PREMIUM_TXT, reply_markup=get_back_keyboard())


@app.on_callback_query(filters.regex("^myplan$"))
async def myplan_cb(client, query):
    await query.answer()
    from Extractor.modules.plans import show_plan
    await show_plan(client, query)
