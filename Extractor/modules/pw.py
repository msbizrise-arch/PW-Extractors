"""
PW (Physics Wallah) Extraction Module - COMPLETE FIXED
Features:
  - Mobile OTP Login (working)
  - Direct Token Login (working)
  - Without Login (keyword search)
  - Batch extraction (videos, notes, DPPs)
"""
import requests
import asyncio
import os
import logging
from pyrogram import filters
from Extractor import app
from SPconfig import PW_ORG_ID, PW_CLIENT_SECRET, PW_BASE_URL, PW_UNIVERSAL_TOKEN, PW_MOBILE_HEADERS

LOGGER = logging.getLogger(__name__)

# ====================== STATES ======================
AWAITING_PHONE = "awaiting_phone"
AWAITING_OTP = "awaiting_otp"
AWAITING_TOKEN = "awaiting_token"
AWAITING_BATCH = "awaiting_batch"
AWAITING_SUBJECTS = "awaiting_subjects"
AWAITING_KEYWORD = "awaiting_keyword"
AWAITING_BATCH_SELECT = "awaiting_batch_select"
AWAITING_SUBJECTS_NL = "awaiting_subjects_nl"
AWAITING_NL_TOKEN = "awaiting_nl_token"

# User data store
user_data = {}

# ====================== HELPERS ======================
def get_headers(token=None):
    """Get API headers with optional token"""
    headers = PW_MOBILE_HEADERS.copy()
    if token:
        headers["authorization"] = f"Bearer {token}"
    return headers


def get_working_token():
    """Get universal token"""
    return PW_UNIVERSAL_TOKEN.strip() if PW_UNIVERSAL_TOKEN else ""


# ====================== CANCEL ======================
@app.on_message(filters.command("cancel") & filters.private)
async def cancel_cmd(client, message):
    """Cancel operation"""
    user_id = message.from_user.id
    if user_id in user_data:
        user_data.pop(user_id, None)
        await message.reply_text("❌ **Cancelled!**\n\nSend /start to begin again.")
    else:
        await message.reply_text("No active operation.\nSend /start to begin.")


# ====================== CONVERSATION HANDLER ======================
@app.on_message(
    filters.text & filters.private &
    ~filters.command(["start", "myplan", "add_premium", "remove_premium", "chk_premium", "cancel", "help"])
)
async def handle_conversation(client, message):
    """Handle all conversation states"""
    user_id = message.from_user.id
    text = message.text.strip()

    if user_id not in user_data:
        return

    state = user_data[user_id].get("state")

    try:
        if state == AWAITING_PHONE:
            await handle_phone(client, message, text)
        elif state == AWAITING_OTP:
            await handle_otp(client, message, text)
        elif state == AWAITING_TOKEN:
            await handle_token(client, message, text)
        elif state == AWAITING_BATCH:
            await handle_batch_select(client, message, text)
        elif state == AWAITING_SUBJECTS:
            await handle_subjects(client, message, text)
        elif state == AWAITING_NL_TOKEN:
            await handle_nl_token(client, message, text)
        elif state == AWAITING_KEYWORD:
            await handle_keyword(client, message, text)
        elif state == AWAITING_BATCH_SELECT:
            await handle_nl_batch_select(client, message, text)
        elif state == AWAITING_SUBJECTS_NL:
            await handle_nl_subjects(client, message, text)

    except Exception as e:
        LOGGER.error(f"Conversation error: {e}", exc_info=True)
        await message.reply_text(f"❌ Error: {str(e)[:200]}\n\nSend /cancel and try again.")
        user_data.pop(user_id, None)


# ====================== OTP LOGIN ======================
async def handle_phone(client, message, phone):
    """Send OTP to phone"""
    user_id = message.from_user.id
    
    # Clean phone
    phone = phone.replace("+91", "").replace(" ", "").replace("-", "")
    if not phone.isdigit() or len(phone) != 10:
        await message.reply_text("❌ Invalid number. Send 10-digit number.\nExample: `9876543210`")
        return

    status = await message.reply_text("📤 Sending OTP...")

    try:
        resp = requests.post(
            f"{PW_BASE_URL}/v3/users/get-otp",
            json={
                "username": f"+91{phone}",
                "organizationId": PW_ORG_ID,
                "otpType": "login",
            },
            headers=PW_MOBILE_HEADERS,
            timeout=15,
        )
        data = resp.json()
        LOGGER.info(f"OTP send: {data}")

        if resp.status_code == 200 and data.get("success", False):
            user_data[user_id]["phone"] = phone
            user_data[user_id]["state"] = AWAITING_OTP
            await status.edit_text("✅ **OTP sent!**\n\n🔢 **Send the OTP you received.**\n\nSend /cancel to abort.")
        elif resp.status_code == 429:
            await status.edit_text("⚠️ **Too many requests. Wait 2-3 minutes and try again.**")
            user_data.pop(user_id, None)
        else:
            err = data.get("message", "Unknown error")
            await status.edit_text(f"❌ **Failed:** {err}\n\nTry again with /start")
            user_data.pop(user_id, None)

    except Exception as e:
        LOGGER.error(f"OTP send error: {e}")
        await status.edit_text("❌ Network error. Try again with /start")
        user_data.pop(user_id, None)


async def handle_otp(client, message, otp):
    """Verify OTP and get token"""
    user_id = message.from_user.id
    phone = user_data[user_id].get("phone", "")
    otp = otp.strip().replace(" ", "")

    if not otp.isdigit():
        await message.reply_text("❌ Invalid OTP. Send numeric OTP.")
        return

    status = await message.reply_text("🔐 Verifying...")

    try:
        resp = requests.post(
            f"{PW_BASE_URL}/v3/oauth/token",
            json={
                "username": f"+91{phone}",
                "otp": otp,
                "client_id": "system-admin",
                "client_secret": PW_CLIENT_SECRET,
                "grant_type": "password",
                "organizationId": PW_ORG_ID,
                "type": "USER",
            },
            headers=PW_MOBILE_HEADERS,
            timeout=15,
        )
        data = resp.json()
        LOGGER.info(f"OTP verify response keys: {list(data.keys())}")

        if "access_token" in data:
            token = data["access_token"]
            user_data[user_id]["token"] = token
            user_data[user_id]["refresh_token"] = data.get("refresh_token", "")
            
            await status.edit_text("✅ **Login Successful!**\n\nFetching your batches...")
            await show_batches(client, message, token)
        else:
            err = data.get("message", "Invalid OTP")
            await status.edit_text(f"❌ **Failed:** {err}\n\nSend /start to restart.")
            user_data.pop(user_id, None)

    except Exception as e:
        LOGGER.error(f"OTP verify error: {e}")
        await status.edit_text("❌ Error. Try again with /start")
        user_data.pop(user_id, None)


# ====================== TOKEN LOGIN ======================
async def handle_token(client, message, token):
    """Handle direct token"""
    user_id = message.from_user.id
    token = token.strip()

    if token.lower().startswith("bearer "):
        token = token[7:].strip()

    user_data[user_id]["token"] = token
    status = await message.reply_text("✅ **Token received!** Fetching batches...")
    await show_batches(client, message, token)


# ====================== SHOW BATCHES ======================
async def show_batches(client, message, token, is_nologin=False):
    """Show user's batches"""
    user_id = message.chat.id if hasattr(message, 'chat') else message.from_user.id
    headers = get_headers(token)

    try:
        batches = []
        
        # Try my-batches endpoint
        resp = requests.get(
            f"{PW_BASE_URL}/v3/batches/my-batches",
            headers=headers,
            timeout=20,
        )
        data = resp.json()
        batches = data.get("data", [])
        
        # Fallback to all batches
        if not batches:
            resp2 = requests.get(
                f"{PW_BASE_URL}/v3/batches?organizationId={PW_ORG_ID}&page=1&limit=100",
                headers=headers,
                timeout=20,
            )
            data2 = resp2.json()
            batches = data2.get("data", [])

        if not batches:
            await message.reply_text(
                "❌ **No batches found.**\n\n"
                "Token may be invalid.\n"
                "Try **Mobile OTP** login.\n\n"
                "Send /start to try again."
            )
            user_data.pop(user_id, None)
            return

        # Show numbered list
        text = f"**📚 Your Batches ({len(batches)}):**\n\n"
        for i, b in enumerate(batches, 1):
            name = b.get("name", "Unknown")
            text += f"`{i}.` **{name}**\n"

        text += f"\n**Send a number (1-{len(batches)}) to select:**\n_(Send /cancel to abort)_"

        user_data[user_id]["batches"] = batches
        user_data[user_id]["state"] = AWAITING_BATCH_SELECT if is_nologin else AWAITING_BATCH
        await message.reply_text(text)

    except Exception as e:
        LOGGER.error(f"Batch fetch error: {e}")
        await message.reply_text(f"❌ Failed to fetch batches.\nSend /start to try again.")
        user_data.pop(user_id, None)


# ====================== BATCH SELECTION ======================
async def handle_batch_select(client, message, choice):
    """Handle batch selection (login flow)"""
    user_id = message.from_user.id
    batches = user_data[user_id].get("batches", [])
    token = user_data[user_id].get("token", "")

    if not choice.isdigit() or not (1 <= int(choice) <= len(batches)):
        await message.reply_text(f"❌ Send number between 1-{len(batches)}")
        return

    selected = batches[int(choice) - 1]
    batch_id = selected.get("_id", "")
    batch_name = selected.get("name", batch_id)
    
    user_data[user_id]["batch_id"] = batch_id
    user_data[user_id]["batch_name"] = batch_name
    
    await fetch_subjects(client, message, batch_id, batch_name, token, is_nologin=False)


async def fetch_subjects(client, message, batch_id, batch_name, token, is_nologin=False):
    """Fetch subjects for batch"""
    user_id = message.from_user.id
    headers = get_headers(token)

    status = await message.reply_text(f"⏳ Fetching subjects for **{batch_name}**...")

    try:
        resp = requests.get(
            f"{PW_BASE_URL}/v3/batches/{batch_id}/details",
            headers=headers,
            timeout=20,
        )
        details = resp.json()
        subjects = details.get("data", {}).get("subjects", [])

        if not subjects:
            await status.edit_text(f"❌ No subjects found for **{batch_name}**.")
            user_data.pop(user_id, None)
            return

        text = f"**📖 Subjects in {batch_name}:**\n\n"
        for i, s in enumerate(subjects, 1):
            text += f"`{i}.` **{s.get('subject', 'Unknown')}**\n"

        text += f"\n**Send numbers separated by spaces:**\nExample: `1 2 3` or `all`\n\n_(Send /cancel to abort)_"

        user_data[user_id]["subjects"] = subjects
        user_data[user_id]["state"] = AWAITING_SUBJECTS_NL if is_nologin else AWAITING_SUBJECTS
        await status.edit_text(text)

    except Exception as e:
        LOGGER.error(f"Subject fetch error: {e}")
        await status.edit_text(f"❌ Failed to fetch subjects.")
        user_data.pop(user_id, None)


# ====================== SUBJECT SELECTION ======================
async def handle_subjects(client, message, subject_text):
    """Handle subject selection (login flow)"""
    user_id = message.from_user.id
    token = user_data[user_id].get("token", "")
    batch_id = user_data[user_id].get("batch_id", "")
    batch_name = user_data[user_id].get("batch_name", "")
    subjects = user_data[user_id].get("subjects", [])
    
    subject_ids = parse_subjects(subject_text, subjects)
    if not subject_ids:
        await message.reply_text("❌ No valid subjects. Send like `1 2 3` or `all`")
        return

    user_data.pop(user_id, None)
    await extract_content(client, message, headers=get_headers(token), 
                         batch_id=batch_id, batch_name=batch_name, 
                         subjects=subjects, subject_ids=subject_ids)


def parse_subjects(text, subjects):
    """Parse subject selection"""
    text = text.strip().lower()

    if text == "all":
        return [str(s.get("_id", s.get("subjectId", ""))) for s in subjects]

    parts = text.replace(",", " ").split()
    subject_ids = []
    for p in parts:
        p = p.strip()
        if p.isdigit():
            idx = int(p) - 1
            if 0 <= idx < len(subjects):
                sid = str(subjects[idx].get("_id", subjects[idx].get("subjectId", "")))
                if sid:
                    subject_ids.append(sid)

    return subject_ids


# ====================== WITHOUT LOGIN ======================
async def handle_nl_token(client, message, token):
    """Handle token for without-login"""
    user_id = message.from_user.id
    token = token.strip()

    if token.lower().startswith("bearer "):
        token = token[7:].strip()

    user_data[user_id]["nl_token"] = token
    user_data[user_id]["state"] = AWAITING_KEYWORD
    
    await message.reply_text(
        "✅ **Token accepted!**\n\n"
        "Type a **batch keyword** to search:\n"
        "Examples: `Yakeen`, `Arjuna`, `Lakshya`, `Prayas`\n\n"
        "Send /cancel to abort."
    )


async def handle_keyword(client, message, keyword):
    """Search batches by keyword"""
    user_id = message.from_user.id
    nl_token = user_data[user_id].get("nl_token", get_working_token())
    headers = get_headers(nl_token) if nl_token else {}

    status = await message.reply_text(f"🔍 Searching for **\"{keyword}\"**...")

    try:
        results = []
        
        # Search through batches
        for page in range(1, 6):  # Max 5 pages
            resp = requests.get(
                f"{PW_BASE_URL}/v3/batches",
                params={"organizationId": PW_ORG_ID, "page": str(page), "limit": "20"},
                headers=headers,
                timeout=20,
            )
            data = resp.json()
            batches = data.get("data", [])
            
            if not batches:
                break

            kw_lower = keyword.lower()
            for b in batches:
                if kw_lower in b.get("name", "").lower():
                    results.append(b)

            if len(batches) < 20:
                break

        if not results:
            await status.edit_text(
                f"❌ No batches found for **\"{keyword}\"**.\n\n"
                "Try: `Yakeen`, `Arjuna`, `Lakshya`, `Prayas`, `NEET`, `JEE`"
            )
            return

        # Show results
        text = f"**🔍 Found {len(results)} batch(es):**\n\n"
        for i, batch in enumerate(results, 1):
            name = batch.get("name", "Unknown")
            text += f"`{i}.` **{name}**\n"

        text += f"\n**Send a number (1-{len(results)}) to select:**\n_(Send /cancel to abort)_"

        if len(text) > 4000:
            text = text[:3900] + "\n\n... (truncated)"

        user_data[user_id]["nl_batches"] = results
        user_data[user_id]["state"] = AWAITING_BATCH_SELECT
        await status.edit_text(text)

    except Exception as e:
        LOGGER.error(f"Keyword search error: {e}")
        await status.edit_text(f"❌ Search failed. Try again.")


async def handle_nl_batch_select(client, message, choice):
    """Handle batch selection (no-login)"""
    user_id = message.from_user.id
    batches = user_data[user_id].get("nl_batches", [])
    nl_token = user_data[user_id].get("nl_token", get_working_token())

    if not choice.isdigit() or not (1 <= int(choice) <= len(batches)):
        await message.reply_text(f"❌ Send number between 1-{len(batches)}")
        return

    selected = batches[int(choice) - 1]
    batch_id = selected.get("_id", "")
    batch_name = selected.get("name", batch_id)
    
    user_data[user_id]["batch_id"] = batch_id
    user_data[user_id]["batch_name"] = batch_name
    
    await fetch_subjects(client, message, batch_id, batch_name, nl_token, is_nologin=True)


async def handle_nl_subjects(client, message, subject_text):
    """Handle subject selection (no-login)"""
    user_id = message.from_user.id
    nl_token = user_data[user_id].get("nl_token", get_working_token())
    batch_id = user_data[user_id].get("batch_id", "")
    batch_name = user_data[user_id].get("batch_name", "")
    subjects = user_data[user_id].get("subjects", [])
    
    subject_ids = parse_subjects(subject_text, subjects)
    if not subject_ids:
        await message.reply_text("❌ No valid subjects. Send like `1 2 3` or `all`")
        return

    user_data.pop(user_id, None)
    await extract_content(client, message, headers=get_headers(nl_token),
                         batch_id=batch_id, batch_name=batch_name,
                         subjects=subjects, subject_ids=subject_ids)


# ====================== EXTRACTION ENGINE ======================
async def extract_content(client, message, headers, batch_id, batch_name, subjects, subject_ids):
    """Extract all content and send as file"""
    user_id = message.from_user.id
    safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in batch_name)
    filename = f"{safe_name.replace(' ', '_')}_{user_id}.txt"

    try:
        # Initialize file
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"Physics Wallah - {batch_name}\n")
            f.write(f"Batch ID: {batch_id}\n")
            f.write("=" * 60 + "\n\n")

        # Get subject names
        selected_names = []
        for sid in subject_ids:
            name = next(
                (s.get("subject", "Unknown") for s in subjects if str(s.get("_id", s.get("subjectId", ""))) == sid),
                f"Subject-{sid}"
            )
            selected_names.append(name)

        await message.reply_text(
            f"🚀 **Extraction Started!**\n\n"
            f"📚 Batch: **{batch_name}**\n"
            f"📖 Subjects: {len(subject_ids)}\n\n"
            "Please wait..."
        )

        total_videos = 0
        total_notes = 0
        total_dpps = 0

        for idx, sid in enumerate(subject_ids):
            sub_name = selected_names[idx]
            await message.reply_text(f"📚 [{idx+1}/{len(subject_ids)}] **{sub_name}**")

            # Extract videos
            count = await extract_type(filename, headers, batch_id, sid, sub_name, "videos", "📹")
            total_videos += count

            # Extract notes
            count = await extract_type(filename, headers, batch_id, sid, sub_name, "notes", "📄")
            total_notes += count

            # Extract DPPs
            count = await extract_type(filename, headers, batch_id, sid, sub_name, "DppNotes", "📝")
            total_dpps += count

            # Extract DPP videos
            count = await extract_type(filename, headers, batch_id, sid, sub_name, "DppVideos", "🎥")
            total_videos += count

        # Write summary
        with open(filename, "a", encoding="utf-8") as f:
            f.write("\n" + "=" * 60 + "\n")
            f.write(f"EXTRACTION SUMMARY\n")
            f.write(f"Batch: {batch_name}\n")
            f.write(f"Total Videos: {total_videos}\n")
            f.write(f"Total Notes/PDFs: {total_notes}\n")
            f.write(f"Total DPPs: {total_dpps}\n")
            f.write("=" * 60 + "\n")

        # Send file
        if total_videos + total_notes + total_dpps == 0:
            await message.reply_text(f"⚠️ **No content found.**\nToken may not have access.")
            return

        caption = (
            f"✅ **Extraction Complete!**\n\n"
            f"📚 **Batch:** {batch_name}\n"
            f"📹 **Videos:** {total_videos}\n"
            f"📄 **Notes:** {total_notes}\n"
            f"📝 **DPPs:** {total_dpps}\n"
            f"📊 **Total:** {total_videos + total_notes + total_dpps}"
        )
        await client.send_document(message.chat.id, filename, caption=caption)

    except Exception as e:
        LOGGER.error(f"Extraction error: {e}", exc_info=True)
        await message.reply_text(f"❌ Extraction failed.\nSend /start to try again.")
    finally:
        if os.path.exists(filename):
            os.remove(filename)


async def extract_type(filename, headers, batch_id, subject_id, subject_name, content_type, emoji):
    """Extract specific content type"""
    count = 0
    page = 1

    while page <= 50:  # Max 50 pages
        try:
            resp = requests.get(
                f"{PW_BASE_URL}/v3/batches/{batch_id}/subject/{subject_id}/contents",
                params={"page": str(page), "contentType": content_type, "tag": ""},
                headers=headers,
                timeout=20,
            )
            data = resp.json()
            items = data.get("data", [])

            if not items:
                break

            with open(filename, "a", encoding="utf-8") as f:
                f.write(f"\n{emoji} {subject_name} - {content_type} (Page {page})\n")
                f.write("-" * 50 + "\n")

                for item in items:
                    title = item.get("topic", item.get("title", "Untitled"))

                    if content_type in ("videos", "DppVideos"):
                        url = item.get("url", "")
                        if url:
                            f.write(f"{title}: {convert_cdn(url)}\n")
                            count += 1
                        
                        video_details = item.get("videoDetails", {})
                        if video_details:
                            vid_url = video_details.get("videoUrl", "")
                            if vid_url:
                                f.write(f"{title}: {convert_cdn(vid_url)}\n")
                                count += 1

                    elif content_type in ("notes", "DppNotes"):
                        url = item.get("url", "") or item.get("pdfUrl", "") or item.get("fileUrl", "")
                        if url:
                            f.write(f"{title}: {url}\n")
                            count += 1

                        for att in item.get("attachments", []):
                            att_url = att.get("url", att.get("baseUrl", ""))
                            if att_url:
                                f.write(f"  -> {att.get('name', 'file')}: {att_url}\n")
                                count += 1

            page += 1
            await asyncio.sleep(0.2)

        except Exception as e:
            LOGGER.error(f"Extract error: {e}")
            break

    return count


def convert_cdn(url):
    """Convert to CDN link"""
    if not url:
        return url
    
    replacements = {
        "d1d34p8vz63oiq.cloudfront.net": "d26g5bnklkwsh4.cloudfront.net",
        "d2bps9p1kber4v.cloudfront.net": "d26g5bnklkwsh4.cloudfront.net",
        "d3cvwyf9ksu0h5.cloudfront.net": "d26g5bnklkwsh4.cloudfront.net",
        "d1kwv1j9v54g2g.cloudfront.net": "d26g5bnklkwsh4.cloudfront.net",
    }
    
    for old, new in replacements.items():
        url = url.replace(old, new)
    
    return url.strip()
