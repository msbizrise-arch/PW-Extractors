"""
Start Module - Handles /start command and callbacks
✅ Fixed: All callback handlers properly pass user context
✅ Fixed: Premium check integration with plans_db
✅ Fixed: All buttons work correctly with updated pw.py states
✅ Added: Proper error handling for edit_text MESSAGE_NOT_MODIFIED
"""
import logging
from pyrogram import filters, Client
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from Extractor import app
from Extractor.core.script import START_TXT, IMG, HELP_TXT, PREMIUM_TXT
from Extractor.core.func import subscribe, chk_user
from config import OWNER_ID, USE_DATABASE

LOGGER = logging.getLogger(__name__)

# ====================== KEYBOARD LAYOUTS ======================
def get_start_keyboard():
    """Main start menu keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Physics Wallah 🚀", callback_data="pw_menu")],
        [InlineKeyboardButton("💎 My Plan", callback_data="myplan"),
         InlineKeyboardButton("❓ Help", callback_data="help")],
        [InlineKeyboardButton("📢 Updates Channel", url="https://t.me/SmartBoy_ApnaMS")]
    ])

def get_pw_menu_keyboard():
    """PW login method selection keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📱 Mobile + OTP", callback_data="pw_mobile")],
        [InlineKeyboardButton("🔑 Direct Token", callback_data="pw_token")],
        [InlineKeyboardButton("🔓 Without Login", callback_data="pw_nologin")],
        [InlineKeyboardButton("🔙 Back", callback_data="go_start")]
    ])

def get_back_keyboard():
    """Simple back button keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back", callback_data="go_start")]
    ])

def get_premium_required_keyboard():
    """Premium required keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 View Plans", callback_data="plans")],
        [InlineKeyboardButton("🔙 Back", callback_data="go_start")]
    ])

# ====================== /start COMMAND ======================@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client: Client, message: Message):
    """Handle /start command."""
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
            reply_markup=get_start_keyboard(),
        )
    except Exception as e:
        LOGGER.error(f"Start photo error: {e}")
        try:
            await message.reply_text(
                START_TXT.format(user_mention),
                reply_markup=get_start_keyboard(),
            )
        except Exception as e2:
            LOGGER.error(f"Start text fallback error: {e2}")

# ====================== /help COMMAND ======================
@app.on_message(filters.command("help") & filters.private)
async def help_cmd(client: Client, message: Message):
    """Handle /help command."""
    await message.reply_text(HELP_TXT, reply_markup=get_back_keyboard())

# ====================== CALLBACK HANDLERS ======================
@app.on_callback_query(filters.regex("^check_sub$"))
async def check_sub_cb(client: Client, query: CallbackQuery):
    """Check subscription again after joining channel."""
    try:
        await query.answer()
        await query.message.delete()
        await client.send_message(query.from_user.id, "/start")
    except Exception as e:
        LOGGER.error(f"check_sub_cb error: {e}")
        if "MESSAGE_NOT_MODIFIED" not in str(e):
            await query.answer("Error! Send /start manually.", show_alert=True)

@app.on_callback_query(filters.regex("^pw_menu$"))
async def pw_menu_cb(client: Client, query: CallbackQuery):
    """Show PW menu with login method options."""
    try:        await query.answer()
        user_id = query.from_user.id
        
        # OWNER always has access
        if user_id == OWNER_ID and OWNER_ID != 0:
            await _safe_edit(query, 
                "**🔐 Choose Login Method:**\n\n"
                "📱 **Mobile + OTP** — Login with your PW registered number\n"
                "🔑 **Direct Token** — Paste your PW bearer token\n"
                "🔓 **Without Login** — Search & extract batches directly",
                get_pw_menu_keyboard()
            )
            return
        
        # Check premium access
        not_allowed = await chk_user(user_id)
        if not_allowed:
            await query.answer("You need premium access!", show_alert=True)
            await _safe_edit(query,
                "**💎 Premium Required!**\n\n"
                "You need to purchase a plan to use this feature.\n"
                "Contact admin to get premium access!",
                get_premium_required_keyboard()
            )
            return
        
        await _safe_edit(query,
            "**🔐 Choose Login Method:**\n\n"
            "📱 **Mobile + OTP** — Login with your PW registered number\n"
            "🔑 **Direct Token** — Paste your PW bearer token\n"
            "🔓 **Without Login** — Search & extract batches directly",
            get_pw_menu_keyboard()
        )
    except Exception as e:
        LOGGER.error(f"pw_menu_cb error: {e}")
        if "MESSAGE_NOT_MODIFIED" not in str(e):
            await query.answer("Error occurred! Try /start", show_alert=True)

async def _safe_edit(query: CallbackQuery, text: str, reply_markup=None):
    """Safely edit message, handling MESSAGE_NOT_MODIFIED error."""
    try:
        await query.message.edit_text(text, reply_markup=reply_markup)
    except Exception as e:
        if "MESSAGE_NOT_MODIFIED" not in str(e):
            raise
        LOGGER.debug(f"Message not modified (same content): {query.message.id}")

@app.on_callback_query(filters.regex("^go_start$"))
async def go_start_cb(client: Client, query: CallbackQuery):
    """Back to start menu."""    try:
        await query.answer()
        user_mention = query.from_user.mention if query.from_user else "User"
        
        try:
            await query.message.delete()
        except Exception:
            pass
        
        try:
            await client.send_photo(
                query.from_user.id,
                IMG[0],
                caption=START_TXT.format(user_mention),
                reply_markup=get_start_keyboard(),
            )
        except Exception:
            await client.send_message(
                query.from_user.id,
                START_TXT.format(user_mention),
                reply_markup=get_start_keyboard(),
            )
    except Exception as e:
        LOGGER.error(f"go_start_cb error: {e}")

@app.on_callback_query(filters.regex("^help$"))
async def help_cb(client: Client, query: CallbackQuery):
    """Show help text."""
    try:
        await query.answer()
        await _safe_edit(query, HELP_TXT, get_back_keyboard())
    except Exception as e:
        LOGGER.error(f"help_cb error: {e}")

@app.on_callback_query(filters.regex("^pw_mobile$"))
async def pw_mobile_cb(client: Client, query: CallbackQuery):
    """Start mobile OTP login flow."""
    try:
        await query.answer()
        try:
            await query.message.delete()
        except Exception:
            pass
        
        chat_id = query.from_user.id
        from Extractor.modules.pw import user_data, AWAITING_PHONE, pw_mobile
        user_data[chat_id] = {"state": AWAITING_PHONE}
        await pw_mobile(client, query.message)
    except Exception as e:
        LOGGER.error(f"pw_mobile_cb error: {e}")        try:
            await client.send_message(query.from_user.id, f"❌ Error: {str(e)}\n\nSend /start to try again.")
        except Exception:
            pass

@app.on_callback_query(filters.regex("^pw_token$"))
async def pw_token_cb(client: Client, query: CallbackQuery):
    """Start direct token login flow."""
    try:
        await query.answer()
        try:
            await query.message.delete()
        except Exception:
            pass
        
        chat_id = query.from_user.id
        from Extractor.modules.pw import user_data, AWAITING_TOKEN, pw_token
        user_data[chat_id] = {"state": AWAITING_TOKEN}
        await pw_token(client, query.message)
    except Exception as e:
        LOGGER.error(f"pw_token_cb error: {e}")
        try:
            await client.send_message(query.from_user.id, f"❌ Error: {str(e)}\n\nSend /start to try again.")
        except Exception:
            pass

@app.on_callback_query(filters.regex("^pw_nologin$"))
async def pw_nologin_cb(client: Client, query: CallbackQuery):
    """Start without login flow."""
    try:
        await query.answer()
        try:
            await query.message.delete()
        except Exception:
            pass
        
        chat_id = query.from_user.id
        from Extractor.modules.pw import user_data, AWAITING_KEYWORD, AWAITING_NL_TOKEN, pw_nologin
        user_data[chat_id] = {"state": AWAITING_KEYWORD}  # Will be updated in pw_nologin
        await pw_nologin(client, query.message)
    except Exception as e:
        LOGGER.error(f"pw_nologin_cb error: {e}")
        try:
            await client.send_message(query.from_user.id, f"❌ Error: {str(e)}\n\nSend /start to try again.")
        except Exception:
            pass

@app.on_callback_query(filters.regex("^plans$"))
async def plans_cb(client: Client, query: CallbackQuery):
    """Show premium plans."""    try:
        await query.answer()
        await _safe_edit(query, PREMIUM_TXT, get_back_keyboard())
    except Exception as e:
        LOGGER.error(f"plans_cb error: {e}")

@app.on_callback_query(filters.regex("^myplan$"))
async def myplan_cb(client: Client, query: CallbackQuery):
    """Handle My Plan button."""
    try:
        await query.answer()
        from Extractor.modules.plans import show_plan
        await show_plan(client, query)
    except Exception as e:
        LOGGER.error(f"myplan_cb error: {e}")
        await query.answer("Error checking plan!", show_alert=True)
