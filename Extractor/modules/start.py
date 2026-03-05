from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from Extractor import app
from Extractor.core.script import START_TXT, IMG, HELP_TXT
from Extractor.core.func import subscribe, chk_user
from Extractor.modules.pw import pw_mobile, pw_token

@app.on_message(filters.command("start"))
async def start(client, message):
    """Handle /start command"""
    # Check channel subscription
    if await subscribe(client, message):
        return
    
    # Send welcome message with buttons
    await message.reply_photo(
        IMG[0],
        caption=START_TXT.format(message.from_user.mention),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔥 Physics Wallah", callback_data="pw_menu")],
            [InlineKeyboardButton("💎 My Plan", callback_data="myplan"),
             InlineKeyboardButton("❓ Help", callback_data="help")],
            [InlineKeyboardButton("📢 Updates Channel", url="https://t.me/SmartBoy_Apnams")]
        ])
    )

@app.on_callback_query(filters.regex("check_sub"))
async def check_sub_cb(client, query):
    """Check subscription again"""
    await query.message.delete()
    await start(client, query.message)

@app.on_callback_query(filters.regex("pw_menu"))
async def pw_menu_cb(client, query):
    """Show PW menu"""
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
            [InlineKeyboardButton("🔙 Back", callback_data="start")]
        ])
    )

@app.on_callback_query(filters.regex("start"))
async def start_cb(client, query):
    """Back to start"""
    await query.message.delete()
    await start(client, query.message)

@app.on_callback_query(filters.regex("help"))
async def help_cb(client, query):
    """Show help"""
    await query.message.edit_text(
        HELP_TXT,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="start")]
        ])
    )

@app.on_callback_query(filters.regex("pw_mobile"))
async def pw_mobile_cb(client, query):
    """Handle mobile login"""
    await query.message.delete()
    await pw_mobile(client, query.message)

@app.on_callback_query(filters.regex("pw_token"))
async def pw_token_cb(client, query):
    """Handle token login"""
    await query.message.delete()
    await pw_token(client, query.message)

@app.on_callback_query(filters.regex("plans"))
async def plans_cb(client, query):
    """Show plans"""
    from Extractor.core.script import PREMIUM_TXT
    await query.message.edit_text(
        PREMIUM_TXT,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="start")]
        ])
    )
