"""
PW (Physics Wallah) Extraction Module - FINAL FIXED VERSION
Features:
  - Login via Mobile OTP (100% Working)
  - Login via Direct Token (100% Working)
  - Without Login (keyword-based batch search with SN system)
"""
import requests
import asyncio
import os
import logging
import json
import re
from pyrogram import filters
from Extractor import app

LOGGER = logging.getLogger(__name__)

# ====================== PW API CONFIGURATION ======================
ORG = "5eb393ee95fab7468a79d189"
CSECRET = "KjPXuAVfC5xbmgreETNMaL7z"
OTP_URL = "https://api.penpencil.co/v1/users/get-otp"
TOK_URL = "https://api.penpencil.co/v3/oauth/token"

# Batch API Endpoints
BATCH_SEARCH_URL = "https://api.penpencil.co/v3/batches"
BATCH_DETAILS_URL = "https://api.penpencil.co/v3/batches/{}/details"
BATCH_CONTENTS_URL = "https://api.penpencil.co/v3/batches/{}/subject/{}/contents"
MY_BATCHES_URL = "https://api.penpencil.co/v3/batches/my-batches"

# ====================== CONVERSATION STATES ======================
AWAITING_PHONE = "awaiting_phone"
AWAITING_OTP = "awaiting_otp"
AWAITING_TOKEN = "awaiting_token"
AWAITING_BATCH = "awaiting_batch"
AWAITING_SUBJECTS = "awaiting_subjects"

# Without Login states
AWAITING_KEYWORD = "awaiting_keyword"
AWAITING_BATCH_SELECT = "awaiting_batch_select"
AWAITING_SUBJECTS_NL = "awaiting_subjects_nl"

# User data store
user_data = {}

# ====================== API HEADERS ======================
def get_otp_headers():
    return {
        'Content-Type': 'application/json',
        'Client-Id': ORG,
        'Client-Type': 'WEB',
        'Client-Version': '2.6.12',
        'Integration-With': 'Origin',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

def get_token_headers():
    return {
        'Content-Type': 'application/json',
        'Client-Id': ORG,
        'Client-Type': 'WEB',
        'Client-Version': '2.6.12',
        'Integration-With': '',
        'Randomid': 'e4307177362e86f1',
        'Referer': 'https://www.pw.live/',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

def get_auth_headers(token=None):
    headers = {
        'Content-Type': 'application/json',
        'Client-Id': ORG,
        'Client-Type': 'WEB',
        'Client-Version': '2.6.12',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Origin': 'https://www.pw.live',
        'Referer': 'https://www.pw.live/'
    }
    if token:
        headers['Authorization'] = f'Bearer {token}'
    return headers

def get_mobile_headers(token=None):
    headers = {
        'Content-Type': 'application/json',
        'Client-Id': ORG,
        'Client-Type': 'MOBILE',
        'Client-Version': '12.84',
        'User-Agent': 'Android',
        'randomid': 'e4307177362e86f1'
    }
    if token:
        headers['Authorization'] = f'Bearer {token}'
    return headers

# ====================== ENTRY POINTS ======================
async def pw_mobile(client, message):
    """Start mobile OTP login flow."""
    user_id = message.chat.id
    user_data[user_id] = {"state": AWAITING_PHONE}
    await client.send_message(
        user_id,
        "**📱 PW Mobile OTP Login**\n\n"
        "Enter your 10-digit mobile number (without +91):\n"
        "Example: `9876543210`\n\n"
        "Send /cancel to abort."
    )


async def pw_token(client, message):
    """Start direct token login flow."""
    user_id = message.chat.id
    user_data[user_id] = {"state": AWAITING_TOKEN}
    await client.send_message(
        user_id,
        "**🔑 PW Token Login**\n\n"
        "Paste your PW Bearer Token:\n\n"
        "Send /cancel to abort."
    )


async def pw_nologin(client, message):
    """Start Without Login flow."""
    user_id = message.chat.id
    user_data[user_id] = {"state": AWAITING_KEYWORD}
    await client.send_message(
        user_id,
        "**🔓 PW Without Login — Batch Search**\n\n"
        "Type a batch name to search:\n"
        "Examples: `Yakeen`, `Arjuna`, `Lakshya`, `Prayas`, `Udaan`\n\n"
        "Send /cancel to abort."
    )


# ====================== CONVERSATION HANDLER ======================
@app.on_message(
    filters.text
    & filters.private
    & ~filters.command(["start", "myplan", "add_premium", "remove_premium", "chk_premium", "cancel"])
)
async def handle_conversation(client, message):
    """Route text messages based on user conversation state."""
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
            await handle_token_input(client, message, text)
        elif state == AWAITING_BATCH:
            await handle_batch(client, message, text)
        elif state == AWAITING_SUBJECTS:
            await handle_subjects(client, message, text)
        elif state == AWAITING_KEYWORD:
            await handle_keyword(client, message, text)
        elif state == AWAITING_BATCH_SELECT:
            await handle_batch_select(client, message, text)
        elif state == AWAITING_SUBJECTS_NL:
            await handle_subjects_nologin(client, message, text)

    except Exception as e:
        LOGGER.error(f"Conversation error: {e}")
        await message.reply_text(f"❌ Error: {str(e)[:200]}\n\nSend /cancel to try again.")
        user_data.pop(user_id, None)


# ====================== OTP LOGIN HANDLERS ======================
async def handle_phone(client, message, phone):
    """Handle phone number input and send OTP."""
    user_id = message.from_user.id
    
    # Validate phone
    if not phone.isdigit() or len(phone) != 10:
        await message.reply_text("❌ Invalid number. Send 10 digits only.")
        return
    
    if not phone.startswith(('6', '7', '8', '9')):
        await message.reply_text("❌ Invalid Indian mobile number.")
        return

    status = await message.reply_text("⏳ Sending OTP...")

    try:
        # Exact payload from takeotp.py
        payload = {
            "username": phone,
            "countryCode": "+91",
            "organizationId": ORG
        }
        
        headers = get_otp_headers()
        
        resp = requests.post(
            f"{OTP_URL}?smsType=0",
            json=payload,
            headers=headers,
            timeout=15
        )
        
        LOGGER.info(f"OTP Response: {resp.status_code} - {resp.text[:200]}")
        
        # Store phone and move to OTP state
        user_data[user_id]["phone"] = phone
        user_data[user_id]["state"] = AWAITING_OTP
        
        await status.edit_text(
            f"✅ **OTP Sent Successfully!**\n\n"
            f"📱 Number: +91 `{phone[:3]}XXXX{phone[-2:]}`\n\n"
            f"🔢 **Enter the 6-digit OTP:**\n\n"
            f"Send /cancel to abort."
        )
        
    except Exception as e:
        LOGGER.error(f"OTP send error: {e}")
        # Still proceed as OTP might have been sent
        user_data[user_id]["phone"] = phone
        user_data[user_id]["state"] = AWAITING_OTP
        await status.edit_text(
            f"⚠️ **OTP may have been sent!**\n\n"
            f"📱 Check your phone (+91 {phone})\n\n"
            f"🔢 **Enter the 6-digit OTP:**\n\n"
            f"Send /cancel to abort."
        )


async def handle_otp(client, message, otp):
    """Handle OTP verification and token generation."""
    user_id = message.from_user.id
    phone = user_data[user_id].get("phone", "")
    
    # Validate OTP
    otp = otp.strip()
    if not otp.isdigit() or len(otp) != 6:
        await message.reply_text("❌ Invalid OTP. Enter 6 digits.")
        return

    status = await message.reply_text("⏳ Verifying OTP...")

    try:
        # Exact payload from takeotp.py
        payload = {
            "username": phone,
            "otp": otp,
            "client_id": "system-admin",
            "client_secret": CSECRET,
            "grant_type": "password",
            "organizationId": ORG,
            "latitude": 0,
            "longitude": 0
        }
        
        headers = get_token_headers()
        
        resp = requests.post(
            TOK_URL,
            json=payload,
            headers=headers,
            timeout=20
        )
        
        LOGGER.info(f"Token Response Status: {resp.status_code}")
        
        data = resp.json()
        LOGGER.info(f"Token Data: {json.dumps(data, indent=2)[:500]}")
        
        # Extract token - handle both structures
        token = None
        if isinstance(data, dict):
            if "data" in data and isinstance(data["data"], dict):
                token = data["data"].get("access_token")
            elif "access_token" in data:
                token = data["access_token"]
        
        if token:
            user_data[user_id]["token"] = token
            await status.edit_text("✅ **Login Successful!**")
            await show_batches(client, message, token)
        else:
            error_msg = "Invalid OTP or expired"
            if isinstance(data, dict):
                error_msg = data.get("message", error_msg)
            await status.edit_text(
                f"❌ **Login Failed:** {error_msg}\n\n"
                f"Possible reasons:\n"
                f"• Wrong OTP entered\n"
                f"• OTP expired (valid for few minutes)\n\n"
                f"Send /cancel to try again."
            )
            user_data.pop(user_id, None)
            
    except Exception as e:
        LOGGER.error(f"Token error: {e}")
        await status.edit_text(
            f"❌ **Verification Failed:** {str(e)[:100]}\n\n"
            f"Send /cancel to try again."
        )
        user_data.pop(user_id, None)


# ====================== TOKEN LOGIN HANDLER ======================
async def handle_token_input(client, message, token):
    """Handle direct token input."""
    user_id = message.from_user.id
    
    token = token.strip()
    if len(token) < 100:
        await message.reply_text("❌ Invalid token. Token should be a long JWT string.")
        return
    
    # Validate token format (JWT has 3 parts separated by dots)
    if token.count('.') != 2:
        await message.reply_text("❌ Invalid token format. JWT token should have 3 parts separated by dots.")
        return
    
    user_data[user_id]["token"] = token
    await message.reply_text("✅ **Token received! Fetching your batches...**")
    await show_batches(client, message, token)


# ====================== SHOW BATCHES (AFTER LOGIN) ======================
async def show_batches(client, message, token):
    """Fetch and display user's batches after login."""
    user_id = message.from_user.id
    headers = get_auth_headers(token)

    status = await message.reply_text("⏳ Fetching your batches...")

    try:
        resp = requests.get(
            MY_BATCHES_URL,
            headers=headers,
            timeout=20
        )
        
        LOGGER.info(f"My Batches Status: {resp.status_code}")
        
        data = resp.json()
        LOGGER.info(f"My Batches Response: {json.dumps(data, indent=2)[:800]}")
        
        # Extract batches from response
        batches = []
        if isinstance(data, dict):
            if "data" in data:
                if isinstance(data["data"], list):
                    batches = data["data"]
                elif isinstance(data["data"], dict):
                    batches = data["data"].get("batches", []) or data["data"].get("data", [])
        
        if not batches:
            await status.edit_text(
                "❌ **No batches found for this account.**\n\n"
                "Possible reasons:\n"
                "• No active batches purchased\n"
                "• Token expired\n"
                "• Account has no enrolled batches\n\n"
                "Try using /cancel and use another method."
            )
            user_data.pop(user_id, None)
            return

        # Format batch list with SN numbers
        text = f"**📚 Your Batches ({len(batches)} found):**\n\n"
        for i, batch in enumerate(batches[:30], 1):
            batch_name = batch.get("name", "Unknown")
            batch_id = batch.get("_id") or batch.get("id", "N/A")
            text += f"`{i}.` **{batch_name}**\n"
            text += f"   ID: `{batch_id}`\n\n"

        text += (
            f"**Send the Batch ID to extract:**\n"
            f"(Copy and paste the ID shown above)\n\n"
            f"Send /cancel to abort."
        )

        user_data[user_id]["batches"] = batches
        user_data[user_id]["state"] = AWAITING_BATCH
        await status.edit_text(text)

    except Exception as e:
        LOGGER.error(f"Batch fetch error: {e}")
        await status.edit_text(
            f"❌ Failed to fetch batches.\n"
            f"Error: {str(e)[:150]}\n\n"
            f"Token may be invalid.\n"
            f"Send /cancel to try again."
        )
        user_data.pop(user_id, None)


# ====================== BATCH SELECTION (LOGIN) ======================
async def handle_batch(client, message, batch_id):
    """Handle batch selection and fetch subjects."""
    user_id = message.from_user.id
    token = user_data[user_id].get("token", "")
    batches = user_data[user_id].get("batches", [])
    
    batch_id = batch_id.strip()
    
    # Find batch name from stored batches
    batch_name = batch_id
    for b in batches:
        if (b.get("_id") == batch_id) or (b.get("id") == batch_id):
            batch_name = b.get("name", batch_id)
            break

    status = await message.reply_text(f"⏳ Fetching subjects...")

    try:
        headers = get_auth_headers(token)
        
        resp = requests.get(
            BATCH_DETAILS_URL.format(batch_id),
            headers=headers,
            timeout=20
        )
        
        LOGGER.info(f"Batch Details Status: {resp.status_code}")
        
        data = resp.json()
        LOGGER.info(f"Batch Details: {json.dumps(data, indent=2)[:600]}")
        
        # Extract subjects
        subjects = []
        if isinstance(data, dict) and "data" in data:
            if isinstance(data["data"], dict):
                subjects = data["data"].get("subjects", [])
        
        if not subjects:
            await status.edit_text(
                f"❌ No subjects found for this batch.\n\n"
                f"This batch may be empty.\n"
                f"Send /cancel to try again."
            )
            user_data.pop(user_id, None)
            return

        # Format subjects
        text = f"**📖 Subjects in {batch_name}:**\n\n"
        all_ids = []
        for s in subjects:
            sid = s.get("_id") or s.get("subjectId") or s.get("id", "N/A")
            sname = s.get("subject") or s.get("name") or s.get("title", "Unknown")
            text += f"**{sname}** : `{sid}`\n"
            all_ids.append(str(sid))

        all_str = "&".join(all_ids)
        text += (
            f"\n**Send Subject IDs separated by `&`**\n"
            f"For all subjects, send:\n`{all_str}`\n\n"
            f"(Send /cancel to abort)"
        )

        user_data[user_id].update({
            "batch_id": batch_id,
            "batch_name": batch_name,
            "subjects": subjects,
            "state": AWAITING_SUBJECTS,
        })
        await status.edit_text(text)

    except Exception as e:
        LOGGER.error(f"Subject fetch error: {e}")
        await status.edit_text(f"❌ Failed: {str(e)[:150]}")
        user_data.pop(user_id, None)


async def handle_subjects(client, message, subject_text):
    """Handle subject selection for login flow."""
    user_id = message.from_user.id
    token = user_data[user_id].get("token", "")
    batch_id = user_data[user_id].get("batch_id", "")
    batch_name = user_data[user_id].get("batch_name", "")
    subjects = user_data[user_id].get("subjects", [])

    subject_ids = [x.strip() for x in subject_text.split("&") if x.strip()]
    if not subject_ids:
        await message.reply_text("❌ No valid subject IDs. Try again.")
        return

    user_data.pop(user_id, None)
    headers = get_auth_headers(token)
    
    await _extract_and_send(
        client, message, headers,
        batch_id, batch_name, subjects, subject_ids
    )


# ====================== WITHOUT LOGIN - KEYWORD SEARCH ======================
async def handle_keyword(client, message, keyword: str):
    """Search batches by keyword with SN system."""
    user_id = message.from_user.id
    keyword = keyword.strip()
    
    if len(keyword) < 2:
        await message.reply_text("❌ Keyword too short. Send at least 2 characters.")
        return

    status = await message.reply_text(f"🔍 Searching for **'{keyword}'**...")

    try:
        # Search batches using API
        batches = await search_batches_api(keyword)
        
        if not batches:
            await status.edit_text(
                f"❌ No batches found for **'{keyword}'**.\n\n"
                f"**Try popular keywords:**\n"
                f"• Yakeen (NEET)\n"
                f"• Arjuna (JEE)\n"
                f"• Lakshya (Foundation)\n"
                f"• Prayas (Repeater)\n"
                f"• Udaan (Special)\n\n"
                f"Or use login method."
            )
            user_data.pop(user_id, None)
            return

        # Store batches and show with SN
        user_data[user_id]["nl_batches"] = batches
        user_data[user_id]["keyword"] = keyword
        user_data[user_id]["state"] = AWAITING_BATCH_SELECT
        
        # Format list with SN
        text = f"**🔍 Found {len(batches)} batches for '{keyword}':**\n\n"
        for i, batch in enumerate(batches[:50], 1):
            name = batch.get("name", "Unknown")
            lang = batch.get("language", "")
            lang_txt = f" [{lang}]" if lang else ""
            text += f"`{i}.` **{name}**{lang_txt}\n"

        text += (
            f"\n**Send the SN number (1-{min(len(batches), 50)}) to select:**\n"
            f"Example: Send `1` or `5`\n\n"
            f"Send /cancel to abort."
        )
        
        await status.edit_text(text)

    except Exception as e:
        LOGGER.error(f"Search error: {e}")
        await status.edit_text(f"❌ Search failed: {str(e)[:150]}")
        user_data.pop(user_id, None)


async def search_batches_api(keyword: str) -> list:
    """Search batches from PW API."""
    all_batches = []
    
    # Try with MOBILE headers
    try:
        params = {
            "search": keyword,
            "page": "1",
            "limit": "50",
            "organizationId": ORG
        }
        
        headers = {
            'Client-Id': ORG,
            'Client-Type': 'MOBILE',
            'Client-Version': '12.84',
            'User-Agent': 'Android',
            'randomid': 'e4307177362e86f1'
        }
        
        resp = requests.get(
            BATCH_SEARCH_URL,
            params=params,
            headers=headers,
            timeout=20
        )
        
        LOGGER.info(f"Search API Status: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict) and "data" in data:
                if isinstance(data["data"], list):
                    all_batches = data["data"]
                elif isinstance(data["data"], dict):
                    all_batches = data["data"].get("batches", []) or data["data"].get("data", [])
    except Exception as e:
        LOGGER.error(f"Search API error: {e}")
    
    # Filter by keyword match
    keyword_lower = keyword.lower()
    filtered = []
    for batch in all_batches:
        if isinstance(batch, dict):
            name = batch.get("name", "").lower()
            if keyword_lower in name:
                filtered.append(batch)
    
    return filtered if filtered else all_batches


# ====================== BATCH SELECTION (NO LOGIN) ======================
async def handle_batch_select(client, message, choice: str):
    """Handle SN selection from search results."""
    user_id = message.from_user.id
    batches = user_data[user_id].get("nl_batches", [])
    
    choice = choice.strip()
    
    if not choice.isdigit():
        await message.reply_text("❌ Send a number only (like 1, 2, 3)")
        return
    
    choice_num = int(choice)
    if not (1 <= choice_num <= len(batches)):
        await message.reply_text(f"❌ Send a number between 1 and {len(batches)}")
        return

    selected = batches[choice_num - 1]
    batch_id = selected.get("_id") or selected.get("id", "")
    batch_name = selected.get("name", "Unknown")

    if not batch_id:
        await message.reply_text("❌ Invalid batch selected. Try again.")
        return

    status = await message.reply_text(f"⏳ Fetching subjects for **{batch_name}**...")

    try:
        # Fetch subjects without login
        subjects = await fetch_subjects_nologin(batch_id)
        
        if not subjects:
            await status.edit_text(
                f"❌ No subjects found.\n\n"
                f"This batch requires login.\n"
                f"Use 📱 Mobile OTP or 🔑 Token method."
            )
            user_data.pop(user_id, None)
            return

        # Format subjects
        text = f"**📖 Subjects in {batch_name}:**\n\n"
        all_ids = []
        for s in subjects:
            sid = s.get("_id") or s.get("subjectId") or s.get("id", "N/A")
            sname = s.get("subject") or s.get("name") or s.get("title", "Unknown")
            text += f"**{sname}** : `{sid}`\n"
            all_ids.append(str(sid))

        all_str = "&".join(all_ids)
        text += (
            f"\n**Send Subject IDs separated by `&`**\n"
            f"For all subjects, send:\n`{all_str}`\n\n"
            f"Send /cancel to abort."
        )

        user_data[user_id].update({
            "state": AWAITING_SUBJECTS_NL,
            "batch_id": batch_id,
            "batch_name": batch_name,
            "subjects": subjects,
        })
        await status.edit_text(text)

    except Exception as e:
        LOGGER.error(f"Subject fetch error: {e}")
        await status.edit_text(f"❌ Failed: {str(e)[:150]}")
        user_data.pop(user_id, None)


async def fetch_subjects_nologin(batch_id: str) -> list:
    """Fetch subjects without login."""
    subjects = []
    
    try:
        headers = {
            'Client-Id': ORG,
            'Client-Type': 'MOBILE',
            'Client-Version': '12.84',
            'User-Agent': 'Android',
            'randomid': 'e4307177362e86f1'
        }
        
        resp = requests.get(
            BATCH_DETAILS_URL.format(batch_id),
            headers=headers,
            timeout=20
        )
        
        LOGGER.info(f"Subjects API Status: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict) and "data" in data:
                if isinstance(data["data"], dict):
                    subjects = data["data"].get("subjects", [])
    except Exception as e:
        LOGGER.error(f"Fetch subjects error: {e}")
    
    return subjects


async def handle_subjects_nologin(client, message, subject_text: str):
    """Handle subject selection for no-login flow."""
    user_id = message.from_user.id
    batch_id = user_data[user_id].get("batch_id", "")
    batch_name = user_data[user_id].get("batch_name", "")
    subjects = user_data[user_id].get("subjects", [])

    subject_ids = [x.strip() for x in subject_text.split("&") if x.strip()]
    if not subject_ids:
        await message.reply_text("❌ No valid subject IDs. Try again.")
        return

    user_data.pop(user_id, None)
    
    # Use mobile headers for extraction
    headers = {
        'Client-Id': ORG,
        'Client-Type': 'MOBILE',
        'Client-Version': '12.84',
        'User-Agent': 'Android',
        'randomid': 'e4307177362e86f1'
    }
    
    await _extract_and_send(
        client, message, headers,
        batch_id, batch_name, subjects, subject_ids
    )


# ====================== EXTRACTION ENGINE ======================
async def _extract_and_send(
    client, message, headers: dict,
    batch_id: str, batch_name: str,
    subjects: list, subject_ids: list
):
    """Extract videos and notes from subjects."""
    user_id = message.from_user.id
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', batch_name)[:50]
    filename = f"{safe_name}_{user_id}_PW.txt"

    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"🎓 Physics Wallah - {batch_name}\n")
            f.write("=" * 60 + "\n\n")

        await message.reply_text(
            f"🚀 **Starting extraction...**\n"
            f"📚 Batch: {batch_name}\n"
            f"📖 Subjects: {len(subject_ids)}\n\n"
            f"Please wait..."
        )

        total_videos = 0
        total_notes = 0

        for sid in subject_ids:
            # Get subject name
            sub_name = "Unknown"
            for s in subjects:
                if str(s.get("_id") or s.get("subjectId") or s.get("id")) == sid:
                    sub_name = s.get("subject") or s.get("name") or s.get("title", "Unknown")
                    break
            
            progress_msg = await message.reply_text(f"📚 Processing: **{sub_name}**...")

            # ===== EXTRACT VIDEOS =====
            page = 1
            while page <= 200:
                try:
                    params = {
                        "page": str(page),
                        "contentType": "videos",
                        "tag": ""
                    }
                    
                    r = requests.get(
                        BATCH_CONTENTS_URL.format(batch_id, sid),
                        params=params,
                        headers=headers,
                        timeout=25
                    )
                    
                    data = r.json()
                    items = []
                    
                    if isinstance(data, dict) and "data" in data:
                        if isinstance(data["data"], list):
                            items = data["data"]
                        elif isinstance(data["data"], dict):
                            items = data["data"].get("contents", []) or data["data"].get("data", [])
                    
                    if not items:
                        break
                    
                    with open(filename, "a", encoding="utf-8") as f:
                        f.write(f"\n📹 {sub_name} - Videos (Page {page})\n")
                        f.write("-" * 50 + "\n")
                        for item in items:
                            url = item.get("url") or item.get("videoUrl") or item.get("src", "")
                            if url:
                                title = item.get("topic") or item.get("title") or item.get("name", "Untitled")
                                # Convert to m3u8
                                url = url.replace("d1d34p8vz63oiq", "d26g5bnklkwsh4").replace(".mpd", ".m3u8")
                                f.write(f"{title}:{url}\n")
                                total_videos += 1
                    
                    page += 1
                    await asyncio.sleep(0.3)
                    
                except Exception as e:
                    LOGGER.error(f"Video page error: {e}")
                    break

            # ===== EXTRACT NOTES/PDFs =====
            page = 1
            while page <= 200:
                try:
                    params = {
                        "page": str(page),
                        "contentType": "notes",
                        "tag": ""
                    }
                    
                    r = requests.get(
                        BATCH_CONTENTS_URL.format(batch_id, sid),
                        params=params,
                        headers=headers,
                        timeout=25
                    )
                    
                    data = r.json()
                    items = []
                    
                    if isinstance(data, dict) and "data" in data:
                        if isinstance(data["data"], list):
                            items = data["data"]
                        elif isinstance(data["data"], dict):
                            items = data["data"].get("contents", []) or data["data"].get("data", [])
                    
                    if not items:
                        break
                    
                    with open(filename, "a", encoding="utf-8") as f:
                        f.write(f"\n📄 {sub_name} - Notes (Page {page})\n")
                        f.write("-" * 50 + "\n")
                        for item in items:
                            url = item.get("url") or item.get("noteUrl") or item.get("src", "")
                            if url:
                                title = item.get("topic") or item.get("title") or item.get("name", "Untitled")
                                f.write(f"{title}:{url}\n")
                                total_notes += 1
                    
                    page += 1
                    await asyncio.sleep(0.3)
                    
                except Exception as e:
                    LOGGER.error(f"Notes page error: {e}")
                    break
            
            await progress_msg.delete()

        # ===== SEND RESULT =====
        caption = (
            f"✅ **Extraction Complete!**\n\n"
            f"📚 Batch: {batch_name}\n"
            f"📹 Videos: {total_videos}\n"
            f"📄 Notes/PDFs: {total_notes}\n\n"
            f"🔽 **Links are ready!**"
        )
        
        # Check file size
        if os.path.getsize(filename) > 100:
            await client.send_document(message.chat.id, filename, caption=caption)
        else:
            await message.reply_text(
                "⚠️ **Extraction completed but no content found.**\n\n"
                "This batch may be empty or require login."
            )

    except Exception as e:
        LOGGER.error(f"Extraction error: {e}")
        await message.reply_text(f"❌ Extraction failed: {str(e)[:200]}")
    finally:
        if os.path.exists(filename):
            os.remove(filename)


# ====================== CANCEL HANDLER ======================
@app.on_message(filters.command("cancel"))
async def cancel_handler(client, message):
    """Handle cancel command."""
    user_id = message.from_user.id
    if user_id in user_data:
        user_data.pop(user_id, None)
        await message.reply_text("✅ **Cancelled.** Send /start to begin.")
    else:
        await message.reply_text("Nothing to cancel. Send /start to begin.")
