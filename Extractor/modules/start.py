"""
Start Module - Handles /start command and callbacks
Fixed: Added error handling for all callbacks to prevent crashes
"""
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from Extractor import app
from Extractor.core.script import START_TXT, IMG, HELP_TXT
from Extractor.core.func import subscribe, chk_user
from Extractor.modules.pw import pw_mobile, pw_token, pw_nologin


@app.on_message(filters.command("start"))
async def start(client, message):
    """Handle /start command"""
    # Check channel subscription
    try:
        if await subscribe(client, message):
            return
    except Exception as e:
        print(f"Subscribe check error: {e}")
    
    # Send welcome message with buttons
    try:
        await message.reply_photo(
            IMG[0],
            caption=START_TXT.format(message.from_user.mention),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🚀 Physics Wallah🚀", callback_data="pw_menu")],
                [InlineKeyboardButton("💎 My Plan", callback_data="myplan"),
                 InlineKeyboardButton("❓ Help", callback_data="help")],
                [InlineKeyboardButton("📢 Updates Channel", url="https://t.me/")]
            ])
        )
    except Exception as e:
        print(f"Start message error: {e}")
        # Fallback to text-only message
        await message.reply_text(
            START_TXT.format(message.from_user.mention),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔥 Physics Wallah", callback_data="pw_menu")],
                [InlineKeyboardButton("💎 My Plan", callback_data="myplan"),
                 InlineKeyboardButton("❓ Help", callback_data="help")],
            ])
        )


@app.on_callback_query(filters.regex("check_sub"))
async def check_sub_cb(client, query):
    """Check subscription again"""
    try:
        await query.message.delete()
        await start(client, query.message)
    except Exception as e:
        print(f"check_sub_cb error: {e}")


@app.on_callback_query(filters.regex("pw_menu"))
async def pw_menu_cb(client, query):
    """Show PW menu"""
    try:
        # Check if user is premium
        is_premium = await chk_user(query.from_user.id)
        if is_premium:
            await query.answer("⚠️ You need premium access!", show_alert=True)
            await query.message.edit_text(
                "**💎 Premium Required!**\n\nYou need to purchase a plan to use this feature.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💎 View Plans", callback_data="plans")],
                    [InlineKeyboardButton("🔙 Back", callback_data="start")]
                ])
            )
            return
        
        await query.message.edit_text(
            "**🔐 Choose Login Method**",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📱 Mobile + OTP", callback_data="pw_mobile")],
                [InlineKeyboardButton("🔑 Direct Token", callback_data="pw_token")],
                [InlineKeyboardButton("🔓 Without Login", callback_data="pw_nologin")],
                [InlineKeyboardButton("🔙 Back", callback_data="start")]
            ])
        )
    except Exception as e:
        print(f"pw_menu_cb error: {e}")
        await query.answer("❌ An error occurred!", show_alert=True)


@app.on_callback_query(filters.regex("start"))
async def start_cb(client, query):
    """Back to start"""
    try:
        await query.message.delete()
        await start(client, query.message)
    except Exception as e:
        print(f"start_cb error: {e}")


@app.on_callback_query(filters.regex("help"))
async def help_cb(client, query):
    """Show help"""
    try:
        await query.message.edit_text(
            HELP_TXT,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="start")]
            ])
        )
    except Exception as e:
        print(f"help_cb error: {e}")


@app.on_callback_query(filters.regex("pw_mobile"))
async def pw_mobile_cb(client, query):
    """Handle mobile login"""
    try:
        await query.message.delete()
        await pw_mobile(client, query.message)
    except Exception as e:
        print(f"pw_mobile_cb error: {e}")
        await query.message.reply_text(f"❌ Error: {str(e)}\n\nSend /start to try again.")


@app.on_callback_query(filters.regex("pw_token"))
async def pw_token_cb(client, query):
    """Handle token login"""
    try:
        await query.message.delete()
        await pw_token(client, query.message)
    except Exception as e:
        print(f"pw_token_cb error: {e}")
        await query.message.reply_text(f"❌ Error: {str(e)}\n\nSend /start to try again.")

@app.on_callback_query(filters.regex("^pw_nologin$"))
async def pw_nologin_cb(client, query):
    """Handle without login"""
    try:
        await query.message.delete()
        await pw_nologin(client, query.message)
    except Exception as e:
        print(f"pw_nologin_cb error: {e}")
        await query.message.reply_text(f"❌ Error: {str(e)}\n\nSend /start to try again.")


@app.on_callback_query(filters.regex("plans"))
async def plans_cb(client, query):
    """Show plans"""
    try:
        from Extractor.core.script import PREMIUM_TXT
        await query.message.edit_text(
            PREMIUM_TXT,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="start")]
            ])
        )
    except Exception as e:
        print(f"plans_cb error: {e}")


@app.on_callback_query(filters.regex("myplan"))
async def myplan_cb(client, query):
    """Handle My Plan button"""
    try:
        from Extractor.modules.plans import show_plan
        await show_plan(client, query)
    except Exception as e:
        print(f"myplan_cb error: {e}")
        await query.answer("❌ Error checking plan!", show_alert=True)
