"""
PW (Physics Wallah) Extraction Module
Features:
  - Login via Mobile OTP
  - Login via Direct Token
  - Without Login (keyword-based public batch search) ← NEW
"""
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

# Without Login states
AWAITING_KEYWORD      = "awaiting_keyword"       # user types keyword e.g. "Yakeen"
AWAITING_BATCH_SELECT = "awaiting_batch_select"  # user picks number from search results
AWAITING_SUBJECTS_NL  = "awaiting_subjects_nl"   # subject selection (no-login flow)

# User data store: {user_id: {"state": str, ...}}
user_data = {}

# ====================== PW API HEADERS ======================
def get_pw_headers(token: str) -> dict:
    """Build PW API headers with given token."""
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

# Public headers — no auth token needed for batch search
PUBLIC_HEADERS = {
    "client-id": "5eb393ee95fab7468a79d189",
    "client-version": "12.84",
    "user-agent": "Android",
    "client-type": "MOBILE",
    "content-type": "application/json",
    "randomid": "e4307177362e86f1",
}

# ====================== ENTRY POINTS ======================
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
        "You can find this in:\n"
        "• Browser DevTools (Network tab)\n"
        "• PW App (Advanced users)\n\n"
        "Send /cancel to abort."
    )


async def pw_nologin(client, message):
    """Start Without Login flow — keyword-based public batch search."""
    user_id = message.chat.id
    user_data[user_id] = {"state": AWAITING_KEYWORD}
    await client.send_message(
        user_id,
        "**🔓 Without Login — PW Batch Search**\n\n"
        "Type a **batch keyword** to search all PW batches:\n\n"
        "Examples:\n"
        "• `Yakeen` → Yakeen NEET Hindi 2026, Yakeen NEET 2025...\n"
        "• `Arjuna` → Arjuna JEE 2026, Arjuna NEET...\n"
        "• `Lakshya` → Lakshya JEE, Lakshya NEET...\n\n"
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

    try:
        # ── Login-based states ──────────────────────────────────────
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

        # ── Without Login states ────────────────────────────────────
        elif state == AWAITING_KEYWORD:
            await handle_keyword(client, message, text)
        elif state == AWAITING_BATCH_SELECT:
            await handle_batch_select(client, message, text)
        elif state == AWAITING_SUBJECTS_NL:
            await handle_subjects_nologin(client, message, text)

    except Exception as e:
        LOGGER.error(f"Conversation error: {e}")
        await message.reply_text(f"❌ Error: {str(e)}\n\nSend /cancel to try again.")
        user_data.pop(user_id, None)


# ====================== LOGIN-BASED STATE HANDLERS ======================
async def handle_phone(client, message, phone):
    user_id = message.from_user.id
    if not phone.isdigit() or len(phone) != 10:
        await message.reply_text("❌ Invalid number. Send a 10-digit mobile number.")
        return

    try:
        resp = requests.post(
            "https://api.penpencil.co/v1/users/get-otp",
            json={"phone": phone, "countryCode": "+91"},
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        if resp.status_code == 200:
            user_data[user_id]["phone"] = phone
            user_data[user_id]["state"] = AWAITING_OTP
            await message.reply_text(
                "✅ **OTP sent to your number!**\n"
                "🔢 **Now send the OTP you received.**\n\n"
                "Send /cancel to abort."
            )
        else:
            await message.reply_text(
                f"❌ Failed to send OTP (Status: {resp.status_code})\nTry again with /start"
            )
            user_data.pop(user_id, None)
    except Exception as e:
        LOGGER.error(f"OTP error: {e}")
        await message.reply_text("❌ Network error. Try again with /start")
        user_data.pop(user_id, None)


async def handle_otp(client, message, otp):
    user_id = message.from_user.id
    phone = user_data[user_id].get("phone", "")

    try:
        resp = requests.post(
            "https://api.penpencil.co/v3/oauth/token",
            json={
                "username": f"+91{phone}",
                "otp": otp,
                "client_id": "5eb393ee95fab7468a79d189",
                "client_secret": "KjPXuAVfC5xbmgreETNMaL7z",
                "grant_type": "password",
            },
            headers={"Content-Type": "application/json"},
            timeout=15
        ).json()

        if "access_token" in resp:
            token = resp["access_token"]
            user_data[user_id]["token"] = token
            await message.reply_text("✅ **Login successful!**")
            await show_batches(client, message, token)
        else:
            error_msg = resp.get("message", "Unknown error")
            await message.reply_text(
                f"❌ **Login failed:** {error_msg}\nTry again with /start"
            )
            user_data.pop(user_id, None)
    except Exception as e:
        LOGGER.error(f"Token error: {e}")
        await message.reply_text("❌ Token error. Try again with /start")
        user_data.pop(user_id, None)


async def handle_token_input(client, message, token):
    user_id = message.from_user.id
    user_data[user_id]["token"] = token
    await message.reply_text("✅ **Token received! Fetching batches...**")
    await show_batches(client, message, token)


async def show_batches(client, message, token):
    user_id = message.from_user.id
    headers = get_pw_headers(token)

    try:
        resp = requests.get(
            "https://api.penpencil.co/v3/batches/my-batches",
            headers=headers, timeout=20
        ).json()

        batches = resp.get("data", [])
        if not batches:
            await message.reply_text("❌ No batches found for this account.")
            user_data.pop(user_id, None)
            return

        text = "**📚 Your Batches:**\n\n"
        for i, d in enumerate(batches, 1):
            text += f"{i}. **{d['name']}**\n   ID: `{d['_id']}`\n\n"
        text += "**Send the Batch ID you want to extract:**\n(Send /cancel to abort)"

        user_data[user_id]["batches"] = batches
        user_data[user_id]["state"] = AWAITING_BATCH
        await message.reply_text(text)

    except Exception as e:
        LOGGER.error(f"Batch fetch error: {e}")
        await message.reply_text(
            f"❌ Failed to fetch batches.\nToken may be invalid or expired.\n"
            f"Error: {str(e)[:100]}"
        )
        user_data.pop(user_id, None)


async def handle_batch(client, message, batch_id):
    user_id = message.from_user.id
    token = user_data[user_id].get("token", "")
    batches = user_data[user_id].get("batches", [])
    headers = get_pw_headers(token)
    batch_name = next((d["name"] for d in batches if d["_id"] == batch_id), batch_id)

    try:
        details = requests.get(
            f"https://api.penpencil.co/v3/batches/{batch_id}/details",
            headers=headers, timeout=20
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
            all_ids.append(str(sid))

        all_str = "&".join(all_ids)
        text += (
            f"\n**Send Subject IDs separated by `&`**\n"
            f"For all subjects send: `{all_str}`\n\n"
            f"(Send /cancel to abort)"
        )

        user_data[user_id].update({
            "batch_id": batch_id,
            "batch_name": batch_name,
            "subjects": subjects,
            "state": AWAITING_SUBJECTS,
        })
        await message.reply_text(text)

    except Exception as e:
        LOGGER.error(f"Subject fetch error: {e}")
        await message.reply_text(f"❌ Failed to fetch subjects.\nError: {str(e)[:100]}")
        user_data.pop(user_id, None)


async def handle_subjects(client, message, subject_text):
    user_id    = message.from_user.id
    token      = user_data[user_id].get("token", "")
    batch_id   = user_data[user_id].get("batch_id", "")
    batch_name = user_data[user_id].get("batch_name", "")
    subjects   = user_data[user_id].get("subjects", [])
    headers    = get_pw_headers(token)

    subject_ids = [x.strip() for x in subject_text.split("&") if x.strip()]
    if not subject_ids:
        await message.reply_text("❌ No valid subject IDs received. Try again.")
        return

    user_data.pop(user_id, None)
    await _extract_and_send(
        client, message, headers,
        batch_id, batch_name, subjects, subject_ids
    )


# ====================== WITHOUT LOGIN STATE HANDLERS ======================
async def handle_keyword(client, message, keyword: str):
    """Search PW public batches by keyword and show numbered results."""
    user_id = message.from_user.id
    status = await message.reply_text(f"🔍 Searching batches for **\"{keyword}\"**...")

    try:
        results = []
        page = 1
        while len(results) < 30:  # cap at 30 results
            resp = requests.get(
                "https://api.penpencil.co/v3/batches",
                params={
                    "organizationId": "5eb393ee95fab7468a79d189",
                    "search": keyword,
                    "page": str(page),
                    "limit": "10",
                },
                headers=PUBLIC_HEADERS,
                timeout=20,
            ).json()

            data = resp.get("data", [])
            if not data:
                break
            results.extend(data)
            if len(data) < 10:  # no more pages
                break
            page += 1

        if not results:
            await status.edit_text(
                f"❌ No batches found for **\"{keyword}\"**.\n\n"
                "Try a different keyword:\n"
                "`Yakeen` · `Arjuna` · `Lakshya` · `Prayas` · `Udaan`"
            )
            user_data.pop(user_id, None)
            return

        # Show numbered list
        text = f"**🔍 Found {len(results)} batch(es) for \"{keyword}\":**\n\n"
        for i, batch in enumerate(results, 1):
            name     = batch.get("name", "Unknown")
            language = batch.get("language", "")
            lang_str = f"  `[{language}]`" if language else ""
            text += f"`{i}.` **{name}**{lang_str}\n"

        text += (
            f"\n**Send a number (1–{len(results)}) to select:**\n"
            "_(Send /cancel to abort)_"
        )

        user_data[user_id].update({
            "state":      AWAITING_BATCH_SELECT,
            "keyword":    keyword,
            "nl_batches": results,
        })
        await status.edit_text(text)

    except Exception as e:
        LOGGER.error(f"Keyword search error: {e}")
        await status.edit_text(
            f"❌ Search failed: {str(e)[:100]}\nTry again with /start"
        )
        user_data.pop(user_id, None)


async def handle_batch_select(client, message, choice: str):
    """Handle numbered batch selection from search results."""
    user_id = message.from_user.id
    batches = user_data[user_id].get("nl_batches", [])

    if not choice.isdigit() or not (1 <= int(choice) <= len(batches)):
        await message.reply_text(
            f"❌ Please send a number between **1 and {len(batches)}**.\n"
            "Or send /cancel to abort."
        )
        return

    selected   = batches[int(choice) - 1]
    batch_id   = selected.get("_id", "")
    batch_name = selected.get("name", batch_id)

    status = await message.reply_text(
        f"⏳ Fetching subjects for **{batch_name}**..."
    )

    try:
        resp = requests.get(
            f"https://api.penpencil.co/v3/batches/{batch_id}/details",
            headers=PUBLIC_HEADERS,
            timeout=20,
        ).json()

        subjects = resp.get("data", {}).get("subjects", [])

        if not subjects:
            await status.edit_text(
                f"❌ No subjects found for **{batch_name}**.\n\n"
                "This batch may require login.\n"
                "Try **📱 Mobile OTP** or **🔑 Token** method from /start."
            )
            user_data.pop(user_id, None)
            return

        text = f"**📖 Subjects in {batch_name}:**\n\n"
        all_ids = []
        for s in subjects:
            sid = s.get("_id", s.get("subjectId", ""))
            text += f"**{s['subject']}** : `{sid}`\n"
            all_ids.append(str(sid))

        all_str = "&".join(all_ids)
        text += (
            f"\n**Send Subject IDs separated by `&`**\n"
            f"To get all subjects, send:\n`{all_str}`\n\n"
            f"_(Send /cancel to abort)_"
        )

        user_data[user_id].update({
            "state":      AWAITING_SUBJECTS_NL,
            "batch_id":   batch_id,
            "batch_name": batch_name,
            "subjects":   subjects,
        })
        await status.edit_text(text)

    except Exception as e:
        LOGGER.error(f"Subject fetch (no-login) error: {e}")
        await status.edit_text(f"❌ Failed to fetch subjects.\nError: {str(e)[:100]}")
        user_data.pop(user_id, None)


async def handle_subjects_nologin(client, message, subject_text: str):
    """Subject selection for no-login flow → start extraction."""
    user_id    = message.from_user.id
    batch_id   = user_data[user_id].get("batch_id", "")
    batch_name = user_data[user_id].get("batch_name", "")
    subjects   = user_data[user_id].get("subjects", [])

    subject_ids = [x.strip() for x in subject_text.split("&") if x.strip()]
    if not subject_ids:
        await message.reply_text("❌ No valid subject IDs received. Try again.")
        return

    user_data.pop(user_id, None)
    # No token — use PUBLIC_HEADERS
    await _extract_and_send(
        client, message, PUBLIC_HEADERS,
        batch_id, batch_name, subjects, subject_ids
    )


# ====================== SHARED EXTRACTION ENGINE ======================
async def _extract_and_send(
    client, message, headers: dict,
    batch_id: str, batch_name: str,
    subjects: list, subject_ids: list,
):
    """Common extraction engine used by both login and no-login flows."""
    user_id  = message.from_user.id
    filename = f"{batch_name.replace(' ', '_')}_{user_id}_PW.txt"

    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"🎓 Physics Wallah - {batch_name}\n")
            f.write("=" * 50 + "\n\n")

        await message.reply_text(
            f"🚀 **Starting extraction for {len(subject_ids)} subject(s)...**\n"
            "Please wait, this may take a while!"
        )

        total_videos = 0
        total_notes  = 0

        for sid in subject_ids:
            sub_name = next(
                (s["subject"] for s in subjects
                 if str(s.get("_id", s.get("subjectId", ""))) == sid),
                f"Subject {sid}"
            )
            await message.reply_text(f"📚 Processing: **{sub_name}**")

            # ── Videos ──────────────────────────────────────────────
            page = 1
            while True:
                try:
                    r = requests.get(
                        f"https://api.penpencil.co/v3/batches/{batch_id}/subject/{sid}/contents",
                        params={"page": str(page), "contentType": "videos", "tag": ""},
                        headers=headers, timeout=20,
                    ).json()
                    data = r.get("data", [])
                    if not data:
                        break
                    with open(filename, "a", encoding="utf-8") as f:
                        f.write(f"\n📹 {sub_name} - Videos (Page {page})\n")
                        f.write("-" * 40 + "\n")
                        for item in data:
                            if item.get("url"):
                                title = item.get("topic", item.get("title", "Unknown"))
                                url = (
                                    item["url"]
                                    .replace("d1d34p8vz63oiq", "d26g5bnklkwsh4")
                                    .replace(".mpd", ".m3u8")
                                    .strip()
                                )
                                f.write(f"{title}:{url}\n")
                                total_videos += 1
                    page += 1
                    await asyncio.sleep(0.5)
                except Exception as e:
                    LOGGER.error(f"Video error (sid={sid}, p={page}): {e}")
                    break

            # ── Notes ────────────────────────────────────────────────
            page = 1
            while True:
                try:
                    r = requests.get(
                        f"https://api.penpencil.co/v3/batches/{batch_id}/subject/{sid}/contents",
                        params={"page": str(page), "contentType": "notes", "tag": ""},
                        headers=headers, timeout=20,
                    ).json()
                    data = r.get("data", [])
                    if not data:
                        break
                    with open(filename, "a", encoding="utf-8") as f:
                        f.write(f"\n📄 {sub_name} - Notes (Page {page})\n")
                        f.write("-" * 40 + "\n")
                        for item in data:
                            if item.get("url"):
                                title = item.get("topic", item.get("title", "Unknown"))
                                f.write(f"{title}:{item['url']}\n")
                                total_notes += 1
                    page += 1
                    await asyncio.sleep(0.5)
                except Exception as e:
                    LOGGER.error(f"Notes error (sid={sid}, p={page}): {e}")
                    break

        # ── Send result file ─────────────────────────────────────────
        caption = (
            f"✅ **Extraction Complete!**\n\n"
            f"📚 Batch: {batch_name}\n"
            f"📹 Videos: {total_videos}\n"
            f"📄 Notes: {total_notes}\n\n"
            f"🔽 **Download links are ready!**"
        )
        await client.send_document(message.chat.id, filename, caption=caption)

    except Exception as e:
        LOGGER.error(f"Extraction error: {e}")
        await message.reply_text(f"❌ Extraction failed:\n{str(e)[:200]}")
    finally:
        if os.path.exists(filename):
            os.remove(filename)
