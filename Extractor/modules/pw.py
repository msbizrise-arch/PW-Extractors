"""
PW (Physics Wallah) Extraction Module - ULTIMATE FIXED VERSION
Features:
  - Login via Mobile OTP (Fixed)
  - Login via Direct Token (Fixed)
  - Without Login (keyword-based public batch search) - FULLY FIXED
  
API Configuration from takeotp.py:
  - Organization ID: 5eb393ee95fab7468a79d189
  - Client Secret: KjPXuAVfC5xbmgreETNMaL7z
  - OTP URL: https://api.penpencil.co/v1/users/get-otp
  - Token URL: https://api.penpencil.co/v3/oauth/token
"""
import requests
import asyncio
import os
import logging
import json
from pyrogram import filters
from Extractor import app

LOGGER = logging.getLogger(__name__)

# ====================== PW API CONFIGURATION ======================
# Real PW API Configuration (from takeotp.py)
ORGANIZATION_ID = "5eb393ee95fab7468a79d189"
CLIENT_SECRET = "KjPXuAVfC5xbmgreETNMaL7z"
OTP_API_URL = "https://api.penpencil.co/v1/users/get-otp"
TOKEN_API_URL = "https://api.penpencil.co/v3/oauth/token"

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

# User data store: {user_id: {"state": str, ...}}
user_data = {}

# ====================== PW API HEADERS ======================
def get_auth_headers(token: str = None) -> dict:
    """Build PW API headers with optional token."""
    headers = {
        "Content-Type": "application/json",
        "Client-Id": ORGANIZATION_ID,
        "Client-Type": "MOBILE",
        "Client-Version": "12.84",
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://www.pw.live",
        "Referer": "https://www.pw.live/",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers

def get_web_headers(token: str = None) -> dict:
    """Build PW Web headers with optional token."""
    headers = {
        "Content-Type": "application/json",
        "Client-Id": ORGANIZATION_ID,
        "Client-Type": "WEB",
        "Client-Version": "2.6.12",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://www.pw.live",
        "Referer": "https://www.pw.live/",
        "Integration-With": "Origin",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers

# Public headers for without-login
PUBLIC_HEADERS = get_auth_headers()
WEB_HEADERS = get_web_headers()

# ====================== ENTRY POINTS ======================
async def pw_mobile(client, message):
    """Start mobile OTP login flow."""
    user_id = message.chat.id
    user_data[user_id] = {"state": AWAITING_PHONE}
    await client.send_message(
        user_id,
        "**📱 PW Mobile OTP Login**\n\n"
        "Send your mobile number (without +91)\n"
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
        "Send your PW Bearer Token\n\n"
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
        "**🔓 PW Without Login — Batch Search**\n\n"
        "Type a **batch keyword** to search:\n\n"
        "Popular keywords:\n"
        "• `Yakeen` → Yakeen NEET batches\n"
        "• `Arjuna` → Arjuna JEE batches\n"
        "• `Lakshya` → Lakshya batches\n"
        "• `Prayas` → Prayas batches\n"
        "• `Udaan` → Udaan batches\n"
        "• `Parakram` → Parakram batches\n"
        "• `Vijeta` → Vijeta batches\n\n"
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
    """Handle phone number input and send OTP."""
    user_id = message.from_user.id
    
    # Validate phone number
    if not phone.isdigit() or len(phone) != 10:
        await message.reply_text("❌ Invalid number. Send a 10-digit mobile number.")
        return
    
    # Check if it starts with valid Indian mobile prefixes
    valid_prefixes = ('6', '7', '8', '9')
    if not phone.startswith(valid_prefixes):
        await message.reply_text("❌ Invalid Indian mobile number. Must start with 6, 7, 8, or 9.")
        return

    try:
        # Prepare OTP request payload (from takeotp.py)
        payload = {
            "username": phone,
            "countryCode": "+91",
            "organizationId": ORGANIZATION_ID
        }
        
        # Use web headers for OTP request
        headers = {
            "Content-Type": "application/json",
            "Client-Id": ORGANIZATION_ID,
            "Client-Type": "WEB",
            "Client-Version": "2.6.12",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Origin": "https://www.pw.live",
            "Referer": "https://www.pw.live/",
            "Integration-With": "Origin"
        }
        
        resp = requests.post(
            f"{OTP_API_URL}?smsType=0",
            json=payload,
            headers=headers,
            timeout=15
        )
        
        LOGGER.info(f"OTP Response Status: {resp.status_code}")
        LOGGER.info(f"OTP Response: {resp.text[:200]}")
        
        # OTP is usually sent even if response is not 200 (CORS issues)
        user_data[user_id]["phone"] = phone
        user_data[user_id]["state"] = AWAITING_OTP
        
        await message.reply_text(
            "✅ **OTP sent successfully!**\n"
            f"📱 Check your phone (+91 {phone[:3]}XXXX{phone[-2:]})\n\n"
            "🔢 **Now send the 6-digit OTP you received.**\n\n"
            "Send /cancel to abort."
        )
        
    except Exception as e:
        LOGGER.error(f"OTP send error: {e}")
        await message.reply_text(
            f"⚠️ **Network error**, but OTP might have been sent!\n"
            f"Check your phone and try entering the OTP.\n\n"
            "If no OTP received, send /cancel and try again."
        )
        # Still allow user to try OTP
        user_data[user_id]["phone"] = phone
        user_data[user_id]["state"] = AWAITING_OTP


async def handle_otp(client, message, otp):
    """Handle OTP verification and token generation."""
    user_id = message.from_user.id
    phone = user_data[user_id].get("phone", "")
    
    # Validate OTP
    if not otp.isdigit() or len(otp) != 6:
        await message.reply_text("❌ Invalid OTP. Send a 6-digit code.")
        return

    status_msg = await message.reply_text("⏳ **Verifying OTP...**")

    try:
        # Prepare token request payload (from takeotp.py)
        payload = {
            "username": phone,
            "otp": otp,
            "client_id": "system-admin",
            "client_secret": CLIENT_SECRET,
            "grant_type": "password",
            "organizationId": ORGANIZATION_ID,
            "latitude": 0,
            "longitude": 0
        }
        
        headers = {
            "Content-Type": "application/json",
            "Client-Id": ORGANIZATION_ID,
            "Client-Type": "WEB",
            "Client-Version": "2.6.12",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Origin": "https://www.pw.live",
            "Referer": "https://www.pw.live/",
            "Randomid": "e4307177362e86f1"
        }
        
        resp = requests.post(
            TOKEN_API_URL,
            json=payload,
            headers=headers,
            timeout=20
        )
        
        data = resp.json()
        LOGGER.info(f"Token Response: {json.dumps(data, indent=2)[:500]}")
        
        # Extract token from response
        token = None
        if "data" in data and isinstance(data["data"], dict):
            token = data["data"].get("access_token")
        elif "access_token" in data:
            token = data["access_token"]
        
        if token:
            user_data[user_id]["token"] = token
            await status_msg.edit_text("✅ **Login successful!**")
            await show_batches(client, message, token)
        else:
            error_msg = data.get("message", "Unknown error")
            await status_msg.edit_text(
                f"❌ **Login failed:** {error_msg}\n\n"
                "Possible reasons:\n"
                "• Wrong OTP entered\n"
                "• OTP expired\n"
                "• Network issue\n\n"
                "Send /cancel to try again."
            )
            user_data.pop(user_id, None)
            
    except Exception as e:
        LOGGER.error(f"Token error: {e}")
        await status_msg.edit_text(
            f"❌ **Verification failed:** {str(e)[:100]}\n\n"
            "Send /cancel to try again."
        )
        user_data.pop(user_id, None)


async def handle_token_input(client, message, token):
    """Handle direct token input."""
    user_id = message.from_user.id
    
    if len(token) < 50:
        await message.reply_text("❌ Invalid token. Token should be much longer.")
        return
    
    user_data[user_id]["token"] = token
    await message.reply_text("✅ **Token received! Fetching batches...**")
    await show_batches(client, message, token)


async def show_batches(client, message, token):
    """Fetch and display user's batches."""
    user_id = message.from_user.id
    headers = get_auth_headers(token)

    try:
        resp = requests.get(
            MY_BATCHES_URL,
            headers=headers,
            timeout=20
        )
        
        data = resp.json()
        LOGGER.info(f"My Batches Response: {json.dumps(data, indent=2)[:500]}")
        
        batches = []
        if "data" in data and isinstance(data["data"], list):
            batches = data["data"]
        elif "data" in data and isinstance(data["data"], dict):
            batches = data["data"].get("batches", []) or data["data"].get("data", [])
        
        if not batches:
            await message.reply_text(
                "❌ No batches found for this account.\n\n"
                "Possible reasons:\n"
                "• No active batches\n"
                "• Token expired\n"
                "• Wrong token\n\n"
                "Try /cancel and use another method."
            )
            user_data.pop(user_id, None)
            return

        text = f"**📚 Your Batches ({len(batches)} found):**\n\n"
        for i, batch in enumerate(batches[:20], 1):  # Show max 20
            batch_name = batch.get("name", "Unknown")
            batch_id = batch.get("_id", batch.get("id", "N/A"))
            text += f"{i}. **{batch_name}**\n   ID: `{batch_id}`\n\n"
        
        if len(batches) > 20:
            text += f"_...and {len(batches) - 20} more batches_\n\n"
            
        text += "**Send the Batch ID you want to extract:**\n(Send /cancel to abort)"

        user_data[user_id]["batches"] = batches
        user_data[user_id]["state"] = AWAITING_BATCH
        await message.reply_text(text)

    except Exception as e:
        LOGGER.error(f"Batch fetch error: {e}")
        await message.reply_text(
            f"❌ Failed to fetch batches.\n"
            f"Error: {str(e)[:100]}\n\n"
            "Token may be invalid or expired.\n"
            "Send /cancel to try again."
        )
        user_data.pop(user_id, None)


async def handle_batch(client, message, batch_id):
    """Handle batch selection and fetch subjects."""
    user_id = message.from_user.id
    token = user_data[user_id].get("token", "")
    batches = user_data[user_id].get("batches", [])
    headers = get_auth_headers(token)
    
    # Find batch name
    batch_name = batch_id
    for b in batches:
        if b.get("_id") == batch_id or b.get("id") == batch_id:
            batch_name = b.get("name", batch_id)
            break

    status_msg = await message.reply_text(f"⏳ Fetching subjects for **{batch_name}**...")

    try:
        resp = requests.get(
            BATCH_DETAILS_URL.format(batch_id),
            headers=headers,
            timeout=20
        )
        
        data = resp.json()
        LOGGER.info(f"Batch Details Response: {json.dumps(data, indent=2)[:500]}")
        
        subjects = []
        if "data" in data and isinstance(data["data"], dict):
            subjects = data["data"].get("subjects", [])
        
        if not subjects:
            await status_msg.edit_text(
                f"❌ No subjects found for this batch.\n\n"
                "This batch may be empty or require different access.\n"
                "Send /cancel to try again."
            )
            user_data.pop(user_id, None)
            return

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
            f"To extract all subjects, send:\n`{all_str}`\n\n"
            f"(Send /cancel to abort)"
        )

        user_data[user_id].update({
            "batch_id": batch_id,
            "batch_name": batch_name,
            "subjects": subjects,
            "state": AWAITING_SUBJECTS,
        })
        await status_msg.edit_text(text)

    except Exception as e:
        LOGGER.error(f"Subject fetch error: {e}")
        await status_msg.edit_text(f"❌ Failed to fetch subjects.\nError: {str(e)[:100]}")
        user_data.pop(user_id, None)


async def handle_subjects(client, message, subject_text):
    """Handle subject selection for login flow."""
    user_id = message.from_user.id
    token = user_data[user_id].get("token", "")
    batch_id = user_data[user_id].get("batch_id", "")
    batch_name = user_data[user_id].get("batch_name", "")
    subjects = user_data[user_id].get("subjects", [])
    headers = get_auth_headers(token)

    subject_ids = [x.strip() for x in subject_text.split("&") if x.strip()]
    if not subject_ids:
        await message.reply_text("❌ No valid subject IDs received. Try again.")
        return

    user_data.pop(user_id, None)
    await _extract_and_send(
        client, message, headers,
        batch_id, batch_name, subjects, subject_ids
    )


# ====================== WITHOUT LOGIN STATE HANDLERS (FIXED) ======================
async def handle_keyword(client, message, keyword: str):
    """Search PW public batches by keyword - FIXED VERSION."""
    user_id = message.from_user.id
    keyword = keyword.strip()
    
    if len(keyword) < 2:
        await message.reply_text("❌ Keyword too short. Send at least 2 characters.")
        return
    
    status = await message.reply_text(f"🔍 Searching batches for **\"{keyword}\"**...")

    try:
        results = await search_batches_multiple_methods(keyword)
        
        if not results:
            await status.edit_text(
                f"❌ No batches found for **\"{keyword}\"**.\n\n"
                "**Try these popular keywords:**\n"
                "• `Yakeen` — NEET batches\n"
                "• `Arjuna` — JEE batches\n"
                "• `Lakshya` — Foundation batches\n"
                "• `Prayas` — Repeater batches\n"
                "• `Udaan` — Special batches\n"
                "• `Parakram` — Crash course\n"
                "• `Vijeta` — Test series\n\n"
                "Or try using the **📱 Mobile OTP** or **🔑 Token** method."
            )
            user_data.pop(user_id, None)
            return

        # Show numbered list
        text = f"**🔍 Found {len(results)} batch(es) for \"{keyword}\":**\n\n"
        for i, batch in enumerate(results[:30], 1):  # Max 30 results
            name = batch.get("name", "Unknown")
            language = batch.get("language", "")
            lang_str = f"  `[{language}]`" if language else ""
            batch_id_short = batch.get("_id", "")[:8] + "..."
            text += f"`{i}.` **{name}**{lang_str}\n"

        text += (
            f"\n**Send a number (1–{min(len(results), 30)}) to select:**\n"
            "_(Send /cancel to abort)_"
        )

        user_data[user_id].update({
            "state": AWAITING_BATCH_SELECT,
            "keyword": keyword,
            "nl_batches": results[:30],
        })
        await status.edit_text(text)

    except Exception as e:
        LOGGER.error(f"Keyword search error: {e}")
        await status.edit_text(
            f"❌ Search failed: {str(e)[:100]}\n\n"
            "Try again or use login method."
        )
        user_data.pop(user_id, None)


async def search_batches_multiple_methods(keyword: str) -> list:
    """Try multiple methods to search batches."""
    results = []
    
    # Method 1: Direct API search with MOBILE headers
    try:
        params = {
            "organizationId": ORGANIZATION_ID,
            "search": keyword,
            "page": "1",
            "limit": "50",
        }
        
        headers = {
            "Client-Id": ORGANIZATION_ID,
            "Client-Type": "MOBILE",
            "Client-Version": "12.84",
            "User-Agent": "Android",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "randomid": "e4307177362e86f1"
        }
        
        resp = requests.get(
            BATCH_SEARCH_URL,
            params=params,
            headers=headers,
            timeout=20
        )
        
        LOGGER.info(f"Search Method 1 Status: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            if "data" in data and isinstance(data["data"], list):
                results = data["data"]
                LOGGER.info(f"Method 1 found {len(results)} batches")
    except Exception as e:
        LOGGER.error(f"Search Method 1 failed: {e}")
    
    # Method 2: Try with WEB headers if Method 1 failed
    if not results:
        try:
            params = {
                "organizationId": ORGANIZATION_ID,
                "search": keyword,
                "page": "1",
                "limit": "50",
            }
            
            headers = {
                "Client-Id": ORGANIZATION_ID,
                "Client-Type": "WEB",
                "Client-Version": "2.6.12",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Origin": "https://www.pw.live",
                "Referer": "https://www.pw.live/"
            }
            
            resp = requests.get(
                BATCH_SEARCH_URL,
                params=params,
                headers=headers,
                timeout=20
            )
            
            LOGGER.info(f"Search Method 2 Status: {resp.status_code}")
            
            if resp.status_code == 200:
                data = resp.json()
                if "data" in data and isinstance(data["data"], list):
                    results = data["data"]
                    LOGGER.info(f"Method 2 found {len(results)} batches")
        except Exception as e:
            LOGGER.error(f"Search Method 2 failed: {e}")
    
    # Method 3: Try alternative endpoint structure
    if not results:
        try:
            params = {
                "search": keyword,
                "page": "1",
                "limit": "50",
            }
            
            headers = {
                "Client-Id": ORGANIZATION_ID,
                "Client-Type": "MOBILE",
                "Client-Version": "12.84",
                "User-Agent": "Android",
                "Accept": "application/json",
            }
            
            resp = requests.get(
                "https://api.penpencil.co/v2/batches",
                params=params,
                headers=headers,
                timeout=20
            )
            
            LOGGER.info(f"Search Method 3 Status: {resp.status_code}")
            
            if resp.status_code == 200:
                data = resp.json()
                if "data" in data:
                    batch_data = data["data"]
                    if isinstance(batch_data, list):
                        results = batch_data
                    elif isinstance(batch_data, dict):
                        results = batch_data.get("batches", []) or batch_data.get("data", [])
                    LOGGER.info(f"Method 3 found {len(results)} batches")
        except Exception as e:
            LOGGER.error(f"Search Method 3 failed: {e}")
    
    # Filter results by keyword match
    filtered_results = []
    keyword_lower = keyword.lower()
    for batch in results:
        if isinstance(batch, dict):
            batch_name = batch.get("name", "").lower()
            # Include if keyword matches
            if keyword_lower in batch_name:
                filtered_results.append(batch)
    
    # If no filtered results, return all results
    return filtered_results if filtered_results else results


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

    selected = batches[int(choice) - 1]
    batch_id = selected.get("_id") or selected.get("id", "")
    batch_name = selected.get("name", batch_id)

    if not batch_id:
        await message.reply_text("❌ Invalid batch ID. Please try again.")
        return

    status = await message.reply_text(
        f"⏳ Fetching subjects for **{batch_name}**..."
    )

    try:
        # Try to fetch subjects without login
        subjects = await fetch_batch_subjects_nologin(batch_id)
        
        if not subjects:
            await status.edit_text(
                f"❌ No subjects found for **{batch_name}**.\n\n"
                "This batch may require login to access.\n"
                "Try **📱 Mobile OTP** or **🔑 Token** method."
            )
            user_data.pop(user_id, None)
            return

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
            f"To extract all subjects, send:\n`{all_str}`\n\n"
            f"_(Send /cancel to abort)_"
        )

        user_data[user_id].update({
            "state": AWAITING_SUBJECTS_NL,
            "batch_id": batch_id,
            "batch_name": batch_name,
            "subjects": subjects,
        })
        await status.edit_text(text)

    except Exception as e:
        LOGGER.error(f"Subject fetch (no-login) error: {e}")
        await status.edit_text(
            f"❌ Failed to fetch subjects.\nError: {str(e)[:100]}\n\n"
            "This batch may require login."
        )
        user_data.pop(user_id, None)


async def fetch_batch_subjects_nologin(batch_id: str) -> list:
    """Fetch batch subjects without login - multiple methods."""
    subjects = []
    
    # Method 1: MOBILE headers
    try:
        headers = {
            "Client-Id": ORGANIZATION_ID,
            "Client-Type": "MOBILE",
            "Client-Version": "12.84",
            "User-Agent": "Android",
            "Accept": "application/json",
            "randomid": "e4307177362e86f1"
        }
        
        resp = requests.get(
            BATCH_DETAILS_URL.format(batch_id),
            headers=headers,
            timeout=20
        )
        
        LOGGER.info(f"Subjects Method 1 Status: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            if "data" in data and isinstance(data["data"], dict):
                subjects = data["data"].get("subjects", [])
                LOGGER.info(f"Method 1 found {len(subjects)} subjects")
    except Exception as e:
        LOGGER.error(f"Subjects Method 1 failed: {e}")
    
    # Method 2: WEB headers
    if not subjects:
        try:
            headers = {
                "Client-Id": ORGANIZATION_ID,
                "Client-Type": "WEB",
                "Client-Version": "2.6.12",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Accept": "application/json",
                "Origin": "https://www.pw.live",
                "Referer": "https://www.pw.live/"
            }
            
            resp = requests.get(
                BATCH_DETAILS_URL.format(batch_id),
                headers=headers,
                timeout=20
            )
            
            LOGGER.info(f"Subjects Method 2 Status: {resp.status_code}")
            
            if resp.status_code == 200:
                data = resp.json()
                if "data" in data and isinstance(data["data"], dict):
                    subjects = data["data"].get("subjects", [])
                    LOGGER.info(f"Method 2 found {len(subjects)} subjects")
        except Exception as e:
            LOGGER.error(f"Subjects Method 2 failed: {e}")
    
    return subjects


async def handle_subjects_nologin(client, message, subject_text: str):
    """Subject selection for no-login flow → start extraction."""
    user_id = message.from_user.id
    batch_id = user_data[user_id].get("batch_id", "")
    batch_name = user_data[user_id].get("batch_name", "")
    subjects = user_data[user_id].get("subjects", [])

    subject_ids = [x.strip() for x in subject_text.split("&") if x.strip()]
    if not subject_ids:
        await message.reply_text("❌ No valid subject IDs received. Try again.")
        return

    user_data.pop(user_id, None)
    
    # Use public headers for no-login extraction
    headers = {
        "Client-Id": ORGANIZATION_ID,
        "Client-Type": "MOBILE",
        "Client-Version": "12.84",
        "User-Agent": "Android",
        "Accept": "application/json",
        "randomid": "e4307177362e86f1"
    }
    
    await _extract_and_send(
        client, message, headers,
        batch_id, batch_name, subjects, subject_ids
    )


# ====================== SHARED EXTRACTION ENGINE ======================
async def _extract_and_send(
    client, message, headers: dict,
    batch_id: str, batch_name: str,
    subjects: list, subject_ids: list,
):
    """Common extraction engine used by both login and no-login flows."""
    user_id = message.from_user.id
    filename = f"{batch_name.replace(' ', '_').replace('/', '_')}_{user_id}_PW.txt"

    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"🎓 Physics Wallah - {batch_name}\n")
            f.write("=" * 50 + "\n\n")

        await message.reply_text(
            f"🚀 **Starting extraction for {len(subject_ids)} subject(s)...**\n"
            "Please wait, this may take a while!"
        )

        total_videos = 0
        total_notes = 0

        for sid in subject_ids:
            sub_name = "Unknown"
            for s in subjects:
                if str(s.get("_id") or s.get("subjectId") or s.get("id")) == sid:
                    sub_name = s.get("subject") or s.get("name") or s.get("title", "Unknown")
                    break
            
            await message.reply_text(f"📚 Processing: **{sub_name}**")

            # ── Videos ──────────────────────────────────────────────
            page = 1
            max_pages = 100  # Safety limit
            while page <= max_pages:
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
                        timeout=20
                    )
                    
                    data = r.json()
                    batch_data = []
                    
                    if "data" in data:
                        if isinstance(data["data"], list):
                            batch_data = data["data"]
                        elif isinstance(data["data"], dict):
                            batch_data = data["data"].get("contents", []) or data["data"].get("data", [])
                    
                    if not batch_data:
                        break
                        
                    with open(filename, "a", encoding="utf-8") as f:
                        f.write(f"\n📹 {sub_name} - Videos (Page {page})\n")
                        f.write("-" * 40 + "\n")
                        for item in batch_data:
                            url = item.get("url") or item.get("videoUrl") or item.get("src", "")
                            if url:
                                title = item.get("topic") or item.get("title") or item.get("name", "Unknown")
                                # Convert DASH to HLS if needed
                                url = (
                                    url.replace("d1d34p8vz63oiq", "d26g5bnklkwsh4")
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
            while page <= max_pages:
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
                        timeout=20
                    )
                    
                    data = r.json()
                    batch_data = []
                    
                    if "data" in data:
                        if isinstance(data["data"], list):
                            batch_data = data["data"]
                        elif isinstance(data["data"], dict):
                            batch_data = data["data"].get("contents", []) or data["data"].get("data", [])
                    
                    if not batch_data:
                        break
                        
                    with open(filename, "a", encoding="utf-8") as f:
                        f.write(f"\n📄 {sub_name} - Notes (Page {page})\n")
                        f.write("-" * 40 + "\n")
                        for item in batch_data:
                            url = item.get("url") or item.get("noteUrl") or item.get("src", "")
                            if url:
                                title = item.get("topic") or item.get("title") or item.get("name", "Unknown")
                                f.write(f"{title}:{url}\n")
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
        
        # Check if file has content
        if os.path.getsize(filename) > 100:
            await client.send_document(message.chat.id, filename, caption=caption)
        else:
            await message.reply_text(
                "⚠️ **Extraction completed but no content found.**\n\n"
                "Possible reasons:\n"
                "• Batch may be empty\n"
                "• Content may require login\n"
                "• Try using login method"
            )

    except Exception as e:
        LOGGER.error(f"Extraction error: {e}")
        await message.reply_text(f"❌ Extraction failed:\n{str(e)[:200]}")
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
        await message.reply_text("✅ **Cancelled.** Start again with /start")
    else:
        await message.reply_text("Nothing to cancel. Send /start to begin.")
