from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from Extractor import app
from Extractor.core.script import START_TXT, IMG
from Extractor.core.func import subscribe, chk_user


@app.on_message(filters.command("start") & filters.private)
async def start(client, message):
    if await subscribe(client, message):
        return
    await message.reply_photo(
        IMG[0],
        caption=START_TXT.format(message.from_user.mention),
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🔥 Physics Wallah", callback_data="pw_start")],
                [InlineKeyboardButton("💎 My Plan", callback_data="myplan")],
            ]
        ),
    )


@app.on_callback_query(filters.regex("^pw_start$"))
async def pw_cb(client, query):
    user_id = query.from_user.id
    if await chk_user(user_id):
        await query.answer("❌ You need premium access!", show_alert=True)
        return
    await query.answer()
    await query.message.edit_text(
        "**Choose Login Method:**",
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("📱 Mobile + OTP", callback_data="pw_mobile")],
                [InlineKeyboardButton("🔑 Direct Token", callback_data="pw_token")],
            ]
        ),
    )


@app.on_callback_query(filters.regex("^pw_mobile$"))
async def pw_mobile_cb(client, query):
    from Extractor.modules.pw import pw_mobile

    await query.answer()
    await pw_mobile(client, query.message)


@app.on_callback_query(filters.regex("^pw_token$"))
async def pw_token_cb(client, query):
    from Extractor.modules.pw import pw_token

    await query.answer()
    await pw_token(client, query.message)


@app.on_callback_query(filters.regex("^myplan$"))
async def myplan_cb(client, query):
    from Extractor.modules.plans import show_plan

    await query.answer()
    await show_plan(client, query)
