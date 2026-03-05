import requests
import asyncio
import os
import logging
from pyrogram import filters
from Extractor import app

LOGGER = logging.getLogger(__name__)

# ====================== CONVERSATION STATES ======================
AWAITING_PHONE = "awaiting_phone"
AWAITING_OTP = "awaiting_otp"
AWAITING_TOKEN = "awaiting_token"
AWAITING_BATCH = "awaiting_batch"
AWAITING_SUBJECTS = "awaiting_subjects"

# User data store: {user_id: {"state": str, "phone": str, "token": str, ...}}
user_data = {}


def get_pw_headers(token):
    """Build PW API headers with the given token."""
    return {
        "Host": "api.penpencil.co",
        "authorization": f"Bearer {token}",
        "client-id": "5eb393ee95fab7468a79d189",
        "client-version": "12.84",
        "user-agent": "Android",
        "randomid": "e4307177362e86f1",
        "client-type": "MOBILE",
        "content-type": "application/json",
    }


# ====================== ENTRY POINTS (called from start.py) ======================
async def pw_mobile(client, message):
    """Start mobile OTP login flow."""
    user_id = message.chat.id
    user_data[user_id] = {"state": AWAITING_PHONE}
    await client.send_message(
        user_id,
        "**📱 Send your mobile number (without +91)**\n"
        "Example: `9876543210`\n\n"
        "Send /cancel to abort."
    )


async def pw_token(client, message):
    """Start direct token login flow."""
    user_id = message.chat.id
    user_data[user_id] = {"state": AWAITING_TOKEN}
    await client.send_message(
        user_id,
        "**🔑 Send your PW Bearer Token**\n\n"
        "Send /cancel to abort."
    )


# ====================== CONVERSATION HANDLER ======================
@app.on_message(
    filters.text
    & filters.private
    & ~filters.command(
        ["start", "myplan", "add_premium", "remove_premium", "chk_premium", "cancel"]
    )
)
async def handle_conversation(client, message):
    """Route text messages based on user conversation state."""
    user_id = message.from_user.id
    text = message.text.strip()

    if user_id not in user_data:
        return  # No active conversation

    state = user_data[user_id].get("state")

    if state == AWAITING_PHONE:
        await handle_phone(client, message, text)
    elif state == AWAITING_OTP:
        await handle_otp(client, message, text)
    elif state == AWAITING_TOKEN:
        await handle_token_input(client, message, text)
    elif state == AWAITING_BATCH:
        await handle_batch(client, message, text)
    elif state == AWAITING_SUBJECTS:
        await handle_subjects(client, message, text)


# ====================== STATE HANDLERS ======================
async def handle_phone(client, message, phone):
    """Handle phone number input."""
    user_id = message.from_user.id

    if not phone.isdigit() or len(phone) != 10:
        await message.reply_text("❌ Invalid number. Send a 10-digit mobile number.")
        return

    url = "https://api.penpencil.co/v1/users/get-otp"
    data = {"phone": phone, "countryCode": "+91"}
    headers = {"Content-Type": "application/json"}
    try:
        resp = requests.post(url, json=data, headers=headers)
        if resp.status_code == 200:
            user_data[user_id]["phone"] = phone
            user_data[user_id]["state"] = AWAITING_OTP
            await message.reply_text(
                "✅ OTP sent to your number!\n"
                "🔢 **Now send the OTP you received.**"
            )
        else:
            await message.reply_text("❌ Failed to send OTP. Try again with /start")
            user_data.pop(user_id, None)
    except Exception as e:
        LOGGER.error(f"OTP error: {e}")
        await message.reply_text("❌ Network error. Try again with /start")
        user_data.pop(user_id, None)


async def handle_otp(client, message, otp):
    """Handle OTP input and get token."""
    user_id = message.from_user.id
    phone = user_data[user_id].get("phone", "")

    url = "https://api.penpencil.co/v3/oauth/token"
    data = {
        "username": f"+91{phone}",
        "otp": otp,
        "client_id": "5eb393ee95fab7468a79d189",
        "client_secret": "KjPXuAVfC5xbmgreETNMaL7z",
        "grant_type": "password",
    }
    headers = {"Content-Type": "application/json"}
    try:
        resp = requests.post(url, json=data, headers=headers).json()
        if "access_token" in resp:
            token = resp["access_token"]
            user_data[user_id]["token"] = token
            await message.reply_text("✅ Login successful!")
            await show_batches(client, message, token)
        else:
            await message.reply_text("❌ Wrong OTP or expired. Try again with /start")
            user_data.pop(user_id, None)
    except Exception as e:
        LOGGER.error(f"Token error: {e}")
        await message.reply_text("❌ Token error. Try again with /start")
        user_data.pop(user_id, None)


async def handle_token_input(client, message, token):
    """Handle direct token input."""
    user_id = message.from_user.id
    user_data[user_id]["token"] = token
    await message.reply_text("✅ Token received! Fetching batches...")
    await show_batches(client, message, token)


async def show_batches(client, message, token):
    """Fetch and display user's batches."""
    user_id = message.from_user.id
    headers = get_pw_headers(token)

    try:
        resp = requests.get(
            "https://api.penpencil.co/v3/batches/my-batches",
            headers=headers,
        ).json()
        batches = resp.get("data", [])

        if not batches:
            await message.reply_text("❌ No batches found for this account.")
            user_data.pop(user_id, None)
            return

        text = "**📚 Your Batches:**\n\n"
        for d in batches:
            text += f"**{d['name']}** : `{d['_id']}`\n"
        text += "\n**Send the Batch ID you want to extract:**"

        user_data[user_id]["batches"] = batches
        user_data[user_id]["state"] = AWAITING_BATCH
        await message.reply_text(text)
    except Exception as e:
        LOGGER.error(f"Batch fetch error: {e}")
        await message.reply_text(
            f"❌ Failed to fetch batches. Token may be invalid.\nError: {e}"
        )
        user_data.pop(user_id, None)


async def handle_batch(client, message, batch_id):
    """Handle batch ID selection and show subjects."""
    user_id = message.from_user.id
    token = user_data[user_id].get("token", "")
    batches = user_data[user_id].get("batches", [])
    headers = get_pw_headers(token)

    batch_name = next(
        (d["name"] for d in batches if d["_id"] == batch_id), batch_id
    )

    try:
        details = requests.get(
            f"https://api.penpencil.co/v3/batches/{batch_id}/details",
            headers=headers,
        ).json()
        subjects = details.get("data", {}).get("subjects", [])

        if not subjects:
            await message.reply_text("❌ No subjects found for this batch.")
            user_data.pop(user_id, None)
            return

        text = "**📖 Subjects:**\n\n"
        all_ids = []
        for s in subjects:
            sid = s.get("_id", s.get("subjectId", ""))
            text += f"**{s['subject']}** : `{sid}`\n"
            all_ids.append(sid)

        all_str = "&".join(all_ids)
        text += (
            f"\n**Send Subject IDs separated by `&`**\n"
            f"For all subjects send: `{all_str}`"
        )

        user_data[user_id]["batch_id"] = batch_id
        user_data[user_id]["batch_name"] = batch_name
        user_data[user_id]["state"] = AWAITING_SUBJECTS
        await message.reply_text(text)
    except Exception as e:
        LOGGER.error(f"Subject fetch error: {e}")
        await message.reply_text(f"❌ Failed to fetch subjects.\nError: {e}")
        user_data.pop(user_id, None)


async def handle_subjects(client, message, subject_text):
    """Handle subject selection and start extraction."""
    user_id = message.from_user.id
    token = user_data[user_id].get("token", "")
    batch_id = user_data[user_id].get("batch_id", "")
    batch_name = user_data[user_id].get("batch_name", "")
    headers = get_pw_headers(token)

    subject_ids = [x.strip() for x in subject_text.split("&") if x.strip()]

    if not subject_ids:
        await message.reply_text("❌ No valid subject IDs received. Try again.")
        return

    # Clear conversation state since extraction is starting
    user_data.pop(user_id, None)

    filename = f"{batch_name}_{user_id}_PW_Videos.txt"
    try:
        with open(filename, "w") as f:
            f.write(f"Physics Wallah - {batch_name}\n\n")

        await message.reply_text(
            f"🚀 **Starting extraction for {len(subject_ids)} subject(s)...**\n"
            "Please wait, this may take a while!"
        )

        total_videos = 0
        for sid in subject_ids:
            await message.reply_text(f"📚 Processing Subject: `{sid}`")
            page = 1
            while True:
                params = {"page": str(page), "contentType": "videos"}
                try:
                    r = requests.get(
                        f"https://api.penpencil.co/v3/batches/{batch_id}/subject/{sid}/contents",
                        params=params,
                        headers=headers,
                    ).json()
                except Exception:
                    break

                data = r.get("data", [])
                if not data:
                    break

                for item in data:
                    if item.get("url"):
                        title = item.get("topic", "Unknown")
                        url = (
                            item["url"]
                            .replace("d1d34p8vz63oiq", "d26g5bnklkwsh4")
                            .replace("mpd", "m3u8")
                            .strip()
                        )
                        with open(filename, "a") as f:
                            f.write(f"{title}:{url}\n")
                        total_videos += 1

                page += 1
                await asyncio.sleep(1)

        if total_videos > 0:
            await client.send_document(
                message.chat.id,
                filename,
                caption=(
                    f"✅ **Extraction Complete!**\n"
                    f"📹 Total Videos: {total_videos}\n"
                    f"🔗 Direct M3U8 links ready!"
                ),
            )
        else:
            await message.reply_text(
                "⚠️ No videos found for the selected subjects."
            )
    except Exception as e:
        LOGGER.error(f"Extraction error: {e}")
        await message.reply_text(f"❌ Extraction failed.\nError: {e}")
    finally:
        if os.path.exists(filename):
            os.remove(filename)


# ====================== CANCEL COMMAND ======================
@app.on_message(filters.command("cancel") & filters.private)
async def cancel_cmd(client, message):
    """Cancel active conversation."""
    user_id = message.from_user.id
    if user_id in user_data:
        user_data.pop(user_id, None)
        await message.reply_text("✅ Operation cancelled.")
    else:
        await message.reply_text("No active operation to cancel.")
