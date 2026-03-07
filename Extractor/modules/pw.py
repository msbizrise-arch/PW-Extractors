"""
PW (Physics Wallah) Extraction Module - COMPLETELY FIXED
All states defined, OTP fixed, Token fixed, Without Login fixed
"""
import requests
import asyncio
import os
import logging
import uuid
import json
import base64
import time
import random
import string
from urllib.parse import quote
from datetime import datetime
from pyrogram import filters
from Extractor import app
from config import (
    PW_ORG_ID, PW_CLIENT_SECRET, PW_BASE_URL,
    PW_UNIVERSAL_TOKEN, OWNER_ID
)
from Extractor.core.func import chk_user

LOGGER = logging.getLogger(__name__)

# ====================== CONVERSATION STATES - ALL DEFINED ======================
AWAITING_PHONE = "awaiting_phone"
AWAITING_OTP = "awaiting_otp"
AWAITING_TOKEN = "awaiting_token"
AWAITING_BATCH = "awaiting_batch"
AWAITING_SUBJECTS = "awaiting_subjects"

# Without Login states
AWAITING_KEYWORD = "awaiting_keyword"
AWAITING_BATCH_SELECT = "awaiting_batch_select"
AWAITING_SUBJECTS_NL = "awaiting_subjects_nl"
AWAITING_NL_TOKEN = "awaiting_nl_token"  # ← YEH MISSING THA

# User data store
user_data = {}


# ====================== HELPER FUNCTIONS ======================
def _generate_random_id(length=18):
    """Generate a unique random ID for API requests."""
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


def _generate_randomid():
    """Generate randomid in format: 16 hex chars"""
    return ''.join(random.choices('0123456789abcdef', k=16))


def _get_mobile_headers(token=None):
    """Generate fresh MOBILE headers with dynamic randomid"""
    headers = {
        "Host": "api.penpencil.co",
        "accept": "application/json",
        "client-id": PW_ORG_ID,
        "client-type": "MOBILE",
        "client-version": "14.2.0",  # Updated version
        "user-agent": "Android",
        "randomid": _generate_randomid(),
        "content-type": "application/json",
    }
    if token:
        headers["authorization"] = f"Bearer {token}"
    return headers


def _get_web_headers(token=None):
    """Generate fresh WEB headers"""
    headers = {
        "Host": "api.penpencil.co",
        "accept": "application/json, text/plain, */*",
        "accept-language": "en-US,en;q=0.9",
        "client-id": PW_ORG_ID,
        "client-type": "WEB",
        "client-version": "3.0.11",
        "content-type": "application/json",
        "origin": "https://www.pw.live",
        "referer": "https://www.pw.live/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get_otp_headers():
    """Headers specifically for OTP sending"""
    return {
        "Content-Type": "application/json",
        "Client-Id": PW_ORG_ID,
        "Client-Type": "WEB",
        "Client-Version": "2.6.12",
        "Integration-With": "Origin",
        "Randomid": _generate_randomid(),
    }


def _get_working_token():
    """Return the universal token from env if set"""
    return PW_UNIVERSAL_TOKEN.strip() if PW_UNIVERSAL_TOKEN else ""


# ====================== JWT FUNCTIONS ======================
def _decode_jwt(token):
    """Decode JWT token payload safely."""
    try:
        parts = token.strip().split(".")
        if len(parts) != 3:
            return None
        payload_b64 = parts[1].replace("-", "+").replace("_", "/")
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding
        payload_json = base64.b64decode(payload_b64).decode("utf-8")
        return json.loads(payload_json)
    except Exception as e:
        LOGGER.error(f"JWT decode error: {e}")
        return None


def _get_token_info(token):
    """Extract user info from JWT token."""
    payload = _decode_jwt(token)
    if not payload:
        return None
    u = payload.get("data", {})
    exp = payload.get("exp", 0)
    return {
        "user_id": u.get("_id", ""),
        "name": f"{u.get('firstName', '')} {u.get('lastName', '')}".strip(),
        "mobile": u.get("username", ""),
        "email": u.get("email", ""),
        "expires": time.strftime("%d %b %Y", time.localtime(exp)) if exp else "Unknown",
        "is_valid": int(time.time()) < exp if exp else False,
    }


# ====================== CANCEL HANDLER ======================
@app.on_message(filters.command("cancel") & filters.private)
async def cancel_cmd(client, message):
    """Cancel any ongoing conversation."""
    user_id = message.from_user.id
    if user_id in user_data:
        user_data.pop(user_id, None)
        await message.reply_text("❌ **Cancelled!**\n\nSend /start to begin again.")
    else:
        await message.reply_text("No active operation to cancel.\nSend /start to begin.")


# ====================== OTP LOGIN HANDLERS ======================
async def handle_phone(client, message, phone):
    """Handle phone number input — send OTP via PW API (FIXED)."""
    user_id = message.from_user.id
    
    # Clean phone number
    phone = phone.replace("+91", "").replace(" ", "").replace("-", "")
    if not phone.isdigit() or len(phone) != 10:
        await message.reply_text(
            "❌ Invalid number. Send a **10-digit mobile number**.\n"
            "Example: `9876543210`"
        )
        return

    status = await message.reply_text("📤 Sending OTP...")

    # TRY MULTIPLE ENDPOINTS
    endpoints = [
        {
            "url": f"{PW_BASE_URL}/v1/users/get-otp?smsType=0",
            "json": {
                "username": phone,
                "countryCode": "+91",
                "organizationId": PW_ORG_ID,
            },
            "headers": _get_otp_headers()
        },
        {
            "url": f"{PW_BASE_URL}/v3/users/get-otp",
            "json": {
                "username": f"+91{phone}",
                "organizationId": PW_ORG_ID,
            },
            "headers": {
                "Content-Type": "application/json",
                "client-id": PW_ORG_ID,
                "client-type": "MOBILE",
                "client-version": "14.2.0",
                "randomid": _generate_randomid(),
            }
        }
    ]

    for endpoint in endpoints:
        try:
            resp = requests.post(
                endpoint["url"],
                json=endpoint["json"],
                headers=endpoint["headers"],
                timeout=15,
            )
            
            LOGGER.info(f"OTP endpoint {endpoint['url']} response: {resp.status_code}")
            
            if resp.status_code == 200:
                user_data[user_id] = {
                    "state": AWAITING_OTP,
                    "phone": phone,
                }
                await status.edit_text(
                    "✅ **OTP sent successfully!**\n\n"
                    "🔢 **Now send the 6-digit OTP you received.**\n\n"
                    "⏰ OTP expires in 5 minutes.\n"
                    "Send /cancel to abort."
                )
                return
                
            elif resp.status_code == 429:
                continue  # Try next endpoint
                
        except Exception as e:
            LOGGER.error(f"OTP endpoint error: {e}")
            continue

    # Sab endpoints fail ho gaye
    await status.edit_text(
        "❌ **Failed to send OTP**\n\n"
        "Possible reasons:\n"
        "- PW server is busy\n"
        "- Number not registered with PW\n"
        "- Too many attempts\n\n"
        "**Solutions:**\n"
        "1. Wait 5-10 minutes and try again\n"
        "2. Use **Direct Token** login\n"
        "3. Use **Without Login** feature"
    )


async def handle_otp(client, message, otp):
    """Handle OTP input — verify and get access token."""
    user_id = message.from_user.id
    user_info = user_data.get(user_id, {})
    phone = user_info.get("phone", "")
    
    otp = otp.strip().replace(" ", "")
    if not otp.isdigit() or len(otp) < 4:
        await message.reply_text("❌ Invalid OTP. Send the **6-digit OTP** you received.")
        return

    status = await message.reply_text("🔐 Verifying OTP...")

    # TRY MULTIPLE TOKEN ENDPOINTS
    endpoints = [
        {
            "url": f"{PW_BASE_URL}/v3/oauth/token",
            "json": {
                "username": phone,
                "otp": otp,
                "client_id": "system-admin",
                "client_secret": PW_CLIENT_SECRET,
                "grant_type": "password",
                "organizationId": PW_ORG_ID,
                "latitude": 0,
                "longitude": 0,
            },
            "headers": {
                "Content-Type": "application/json",
                "Client-Id": PW_ORG_ID,
                "Client-Type": "WEB",
                "Client-Version": "2.6.12",
                "Randomid": _generate_randomid(),
            }
        },
        {
            "url": f"{PW_BASE_URL}/v3/oauth/token",
            "json": {
                "username": f"+91{phone}",
                "otp": otp,
                "client_id": "system-admin",
                "client_secret": PW_CLIENT_SECRET,
                "grant_type": "password",
                "organizationId": PW_ORG_ID,
                "type": "USER",
            },
            "headers": {
                "Content-Type": "application/json",
                "client-id": PW_ORG_ID,
                "client-type": "MOBILE",
                "client-version": "14.2.0",
                "randomid": _generate_randomid(),
            }
        }
    ]

    for endpoint in endpoints:
        try:
            resp = requests.post(
                endpoint["url"],
                json=endpoint["json"],
                headers=endpoint["headers"],
                timeout=20,
            )
            
            data = resp.json()
            
            # Extract token from various paths
            token = None
            if data.get("data", {}).get("access_token"):
                token = data["data"]["access_token"]
            elif data.get("access_token"):
                token = data["access_token"]
            elif data.get("token"):
                token = data["token"]
                
            if token:
                user_data[user_id]["token"] = token
                info = _get_token_info(token)
                
                info_text = ""
                if info:
                    status_text = "✅ Valid" if info['is_valid'] else "⚠️ Expired"
                    info_text = f"\n👤 {info['name']}\n🔐 {status_text}"
                
                await status.edit_text(f"✅ **Login Successful!**{info_text}\n\nFetching batches...")
                await show_batches_login(client, message, token)
                return
                
        except Exception as e:
            LOGGER.error(f"Token endpoint error: {e}")
            continue

    await status.edit_text(
        "❌ **OTP Verification Failed**\n\n"
        "Invalid or expired OTP.\n"
        "Send /start to try again."
    )
    user_data.pop(user_id, None)


# ====================== TOKEN LOGIN ======================
async def handle_token_input(client, message, token):
    """Handle direct token input."""
    user_id = message.from_user.id

    token = token.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()

    status = await message.reply_text("🔍 Validating token...")

    # Test token immediately
    try:
        headers = _get_web_headers(token)
        test_resp = requests.get(
            f"{PW_BASE_URL}/v3/batches",
            params={"organizationId": PW_ORG_ID, "limit": "1"},
            headers=headers,
            timeout=10,
        )
        
        if test_resp.status_code == 200:
            await status.edit_text("✅ **Token accepted!** Fetching batches...")
        elif test_resp.status_code == 401:
            await status.edit_text("⚠️ **Token may be invalid** - will try anyway...")
        else:
            await status.edit_text(f"⚠️ **Token response: {test_resp.status_code}** - will try...")
            
    except Exception as e:
        LOGGER.error(f"Token test error: {e}")
        await status.edit_text("⚠️ **Could not validate token** - will attempt to use it...")

    user_data[user_id] = {
        "token": token,
        "state": AWAITING_BATCH  # Directly go to batch selection
    }
    
    await show_batches_login(client, message, token)


# ====================== SHOW BATCHES (LOGIN) ======================
async def show_batches_login(client, message, token):
    """Fetch and display user's batches."""
    user_id = message.chat.id
    batches = []
    
    # TRY MULTIPLE METHODS
    methods = [
        {
            "name": "MOBILE my-batches",
            "url": f"{PW_BASE_URL}/v3/batches/my-batches",
            "headers": _get_mobile_headers(token),
            "params": {}
        },
        {
            "name": "WEB my-batches",
            "url": f"{PW_BASE_URL}/v3/batches/my-batches",
            "headers": _get_web_headers(token),
            "params": {}
        },
        {
            "name": "All batches",
            "url": f"{PW_BASE_URL}/v3/batches",
            "headers": _get_web_headers(token),
            "params": {"organizationId": PW_ORG_ID, "page": "1", "limit": "50"}
        }
    ]

    for method in methods:
        try:
            resp = requests.get(
                method["url"],
                params=method["params"],
                headers=method["headers"],
                timeout=15,
            )
            
            if resp.status_code == 200:
                data = resp.json()
                if method["name"] == "All batches":
                    batches = data.get("data", [])
                else:
                    batches = data.get("data", [])
                    
                if batches:
                    LOGGER.info(f"Found {len(batches)} batches via {method['name']}")
                    break
                    
        except Exception as e:
            LOGGER.error(f"Batch fetch {method['name']} error: {e}")
            continue

    if not batches:
        # Check if token is completely dead
        try:
            test = requests.get(
                f"{PW_BASE_URL}/v3/batches",
                params={"organizationId": PW_ORG_ID, "limit": "1"},
                headers=_get_web_headers(token),
                timeout=10,
            )
            if test.status_code == 401:
                await message.reply_text(
                    "❌ **Invalid Token!**\n\n"
                    "Your token is not authorized.\n\n"
                    "**Solutions:**\n"
                    "1. Get a fresh token from PW website\n"
                    "2. Use OTP login\n"
                    "3. Use Without Login feature"
                )
            else:
                await message.reply_text(
                    "❌ **No Batches Found**\n\n"
                    "Possible reasons:\n"
                    "- No batches purchased on this account\n"
                    "- Token doesn't have batch access\n"
                    "- PW API issue\n\n"
                    "**Try:**\n"
                    "1. Use Without Login feature\n"
                    "2. Login with OTP\n"
                    "3. Use a different token"
                )
        except:
            await message.reply_text(
                "❌ **Failed to fetch batches**\n\n"
                "Please try Without Login feature instead."
            )
        
        user_data.pop(user_id, None)
        return

    # Show batches with numbers
    text = f"**📚 Found {len(batches)} Batches:**\n\n"
    for i, b in enumerate(batches[:20], 1):  # Max 20 to avoid long message
        name = b.get("name", "Unknown")
        text += f"`{i}.` **{name}**\n"

    text += f"\n**Send a number (1-{min(20, len(batches))}) to select:**\n"
    text += "_(Send /cancel to abort)_"

    user_data[user_id].update({
        "batches": batches[:20],
        "state": AWAITING_BATCH
    })
    
    await message.reply_text(text)


# ====================== WITHOUT LOGIN HANDLERS ======================
async def handle_keyword(client, message, keyword):
    """Search PW batches by keyword using universal token."""
    user_id = message.from_user.id
    
    # Get universal token
    universal_token = _get_working_token()
    if not universal_token:
        await message.reply_text(
            "❌ **Universal Token Not Configured**\n\n"
            "Admin needs to set PW_UNIVERSAL_TOKEN in .env file.\n"
            "Please use OTP or Token login for now."
        )
        return

    status = await message.reply_text(f"🔍 Searching for **'{keyword}'**...")

    all_results = []
    page = 1
    
    try:
        while page <= 5:  # Max 5 pages
            headers = _get_web_headers(universal_token)
            resp = requests.get(
                f"{PW_BASE_URL}/v3/batches",
                params={
                    "organizationId": PW_ORG_ID,
                    "page": str(page),
                    "limit": "50",
                    "search": keyword,  # PW API supports search param
                },
                headers=headers,
                timeout=15,
            )

            if resp.status_code != 200:
                break

            data = resp.json()
            batches = data.get("data", [])
            
            if not batches:
                break

            # Filter by keyword (case-insensitive)
            keyword_lower = keyword.lower()
            for batch in batches:
                name = batch.get("name", "")
                if keyword_lower in name.lower():
                    all_results.append(batch)

            if len(batches) < 50:
                break
                
            page += 1
            await asyncio.sleep(0.5)

    except Exception as e:
        LOGGER.error(f"Search error: {e}")

    if not all_results:
        await status.edit_text(
            f"❌ **No batches found for '{keyword}'**\n\n"
            "Try these popular keywords:\n"
            "• `Yakeen` (NEET)\n"
            "• `Arjuna` (JEE)\n"
            "• `Lakshya`\n"
            "• `Prayas`\n"
            "• `NEET`\n"
            "• `JEE`"
        )
        return

    # Show results with numbers
    text = f"**🔍 Found {len(all_results)} batches for '{keyword}':**\n\n"
    for i, batch in enumerate(all_results[:20], 1):
        name = batch.get("name", "Unknown")
        text += f"`{i}.` **{name}**\n"

    text += f"\n**Send a number (1-{min(20, len(all_results))}) to select:**\n"
    text += "_(Send /cancel to abort)_"

    user_data[user_id] = {
        "state": AWAITING_BATCH_SELECT,
        "nl_batches": all_results[:20],
        "nl_token": universal_token,
    }

    await status.edit_text(text)


async def handle_batch_select_nologin(client, message, choice):
    """Handle batch selection for without-login flow."""
    user_id = message.from_user.id
    user_info = user_data.get(user_id, {})
    batches = user_info.get("nl_batches", [])
    nl_token = user_info.get("nl_token", "")

    if not choice.isdigit() or not (1 <= int(choice) <= len(batches)):
        await message.reply_text(
            f"❌ Please send a number between **1 and {len(batches)}**."
        )
        return

    selected = batches[int(choice) - 1]
    batch_id = selected.get("_id", "")
    batch_name = selected.get("name", batch_id)

    user_data[user_id].update({
        "batch_id": batch_id,
        "batch_name": batch_name,
    })

    await _fetch_and_show_subjects(
        client, message, batch_id, batch_name,
        nl_token, user_id, AWAITING_SUBJECTS_NL,
    )


async def handle_batch_select_login(client, message, choice):
    """Handle batch selection for login flow."""
    user_id = message.from_user.id
    user_info = user_data.get(user_id, {})
    batches = user_info.get("batches", [])
    token = user_info.get("token", "")

    if not choice.isdigit() or not (1 <= int(choice) <= len(batches)):
        await message.reply_text(
            f"❌ Please send a number between **1 and {len(batches)}**."
        )
        return

    selected = batches[int(choice) - 1]
    batch_id = selected.get("_id", "")
    batch_name = selected.get("name", batch_id)

    user_data[user_id].update({
        "batch_id": batch_id,
        "batch_name": batch_name,
    })

    await _fetch_and_show_subjects(
        client, message, batch_id, batch_name,
        token, user_id, AWAITING_SUBJECTS,
    )


async def _fetch_and_show_subjects(client, message, batch_id, batch_name, token, user_id, next_state):
    """Fetch subjects for a batch."""
    status = await message.reply_text(f"⏳ Fetching subjects...")

    subjects = []
    
    # Try multiple methods
    for headers_func in [_get_web_headers, _get_mobile_headers]:
        try:
            headers = headers_func(token)
            resp = requests.get(
                f"{PW_BASE_URL}/v3/batches/{batch_id}/details",
                headers=headers,
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                subjects = data.get("data", {}).get("subjects", [])
                if subjects:
                    break
        except:
            continue

    if not subjects:
        await status.edit_text(
            f"❌ **No subjects found** for this batch.\n\n"
            "Try a different batch."
        )
        user_data.pop(user_id, None)
        return

    # Show subjects with numbers
    text = f"**📖 Subjects in {batch_name}:**\n\n"
    for i, s in enumerate(subjects, 1):
        subject_name = s.get('subject', 'Unknown')
        text += f"`{i}.` **{subject_name}**\n"

    text += f"\n**Send numbers (e.g., `1 2 3` or `all`):**\n"
    text += "_(Send /cancel to abort)_"

    user_data[user_id].update({
        "subjects": subjects,
        "state": next_state,
    })
    
    await status.edit_text(text)


async def handle_subjects(client, message, subject_text):
    """Handle subject selection."""
    user_id = message.from_user.id
    user_info = user_data.get(user_id, {})
    token = user_info.get("token", "")
    batch_id = user_info.get("batch_id", "")
    batch_name = user_info.get("batch_name", "")
    subjects = user_info.get("subjects", [])

    # Parse selection
    subject_ids = []
    if subject_text.strip().lower() == "all":
        subject_ids = [s.get("_id", s.get("subjectId", "")) for s in subjects if s.get("_id") or s.get("subjectId")]
    else:
        parts = subject_text.replace(",", " ").split()
        for p in parts:
            if p.isdigit():
                idx = int(p) - 1
                if 0 <= idx < len(subjects):
                    sid = subjects[idx].get("_id", subjects[idx].get("subjectId", ""))
                    if sid:
                        subject_ids.append(sid)

    if not subject_ids:
        await message.reply_text("❌ No valid subjects selected.")
        return

    headers = _get_web_headers(token)
    user_data.pop(user_id, None)
    await _extract_and_send(
        client, message, headers,
        batch_id, batch_name, subjects, subject_ids,
    )


async def handle_subjects_nologin(client, message, subject_text):
    """Handle subject selection for no-login."""
    user_id = message.from_user.id
    user_info = user_data.get(user_id, {})
    batch_id = user_info.get("batch_id", "")
    batch_name = user_info.get("batch_name", "")
    subjects = user_info.get("subjects", [])
    nl_token = user_info.get("nl_token", "")

    # Parse selection
    subject_ids = []
    if subject_text.strip().lower() == "all":
        subject_ids = [s.get("_id", s.get("subjectId", "")) for s in subjects if s.get("_id") or s.get("subjectId")]
    else:
        parts = subject_text.replace(",", " ").split()
        for p in parts:
            if p.isdigit():
                idx = int(p) - 1
                if 0 <= idx < len(subjects):
                    sid = subjects[idx].get("_id", subjects[idx].get("subjectId", ""))
                    if sid:
                        subject_ids.append(sid)

    if not subject_ids:
        await message.reply_text("❌ No valid subjects selected.")
        return

    headers = _get_web_headers(nl_token)
    user_data.pop(user_id, None)
    await _extract_and_send(
        client, message, headers,
        batch_id, batch_name, subjects, subject_ids,
    )


# ====================== EXTRACTION ENGINE ======================
async def _extract_and_send(client, message, headers, batch_id, batch_name, subjects, subject_ids):
    """Extract all content and send as file."""
    user_id = message.from_user.id
    filename = f"PW_{batch_id[:8]}_{user_id}.txt"
    
    total_videos = 0
    total_notes = 0
    
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"PW Extractor - {batch_name}\n")
            f.write(f"Batch ID: {batch_id}\n")
            f.write(f"Date: {datetime.now().strftime('%d %b %Y')}\n")
            f.write("=" * 60 + "\n\n")

        await message.reply_text("🚀 **Extraction started!** This may take a few minutes...")

        for idx, sid in enumerate(subject_ids):
            # Get subject name
            sub_name = "Unknown"
            for s in subjects:
                if str(s.get("_id", s.get("subjectId", ""))) == sid:
                    sub_name = s.get("subject", "Unknown")
                    break
            
            # Extract videos
            vid_count = await _extract_content_type(
                filename, headers, batch_id, sid, sub_name,
                "videos", "📹 VIDEOS"
            )
            total_videos += vid_count
            
            # Extract notes
            note_count = await _extract_content_type(
                filename, headers, batch_id, sid, sub_name,
                "notes", "📄 NOTES"
            )
            total_notes += note_count
            
            # Extract DPPs
            dpp_count = await _extract_content_type(
                filename, headers, batch_id, sid, sub_name,
                "DppNotes", "📝 DPPs"
            )
            total_notes += dpp_count

        # Send file
        if total_videos + total_notes == 0:
            await message.reply_text("⚠️ **No content found** in this batch.")
            return

        caption = f"✅ **Extraction Complete!**\n\n📹 Videos: {total_videos}\n📄 Notes/PDFs: {total_notes}\n📊 Total: {total_videos + total_notes}"
        await client.send_document(message.chat.id, filename, caption=caption)

    except Exception as e:
        LOGGER.error(f"Extraction error: {e}")
        await message.reply_text(f"❌ Extraction failed: {str(e)[:100]}")
    finally:
        if os.path.exists(filename):
            os.remove(filename)


async def _extract_content_type(filename, headers, batch_id, subject_id, subject_name, content_type, header):
    """Extract specific content type."""
    count = 0
    page = 1
    
    with open(filename, "a", encoding="utf-8") as f:
        f.write(f"\n{header} - {subject_name}\n")
        f.write("-" * 40 + "\n")

    while page <= 10:
        try:
            resp = requests.get(
                f"{PW_BASE_URL}/v3/batches/{batch_id}/subject/{subject_id}/contents",
                params={"page": str(page), "contentType": content_type},
                headers=headers,
                timeout=15,
            )
            
            if resp.status_code != 200:
                break
                
            data = resp.json()
            items = data.get("data", [])

            if not items:
                break

            with open(filename, "a", encoding="utf-8") as f:
                for item in items:
                    title = item.get("topic", item.get("title", "Untitled"))
                    
                    if content_type in ("videos", "DppVideos"):
                        url = item.get("url", "") or item.get("videoDetails", {}).get("videoUrl", "")
                        if url:
                            f.write(f"{title}: {url}\n")
                            count += 1
                    else:
                        url = item.get("url", "") or item.get("pdfUrl", "") or item.get("fileUrl", "")
                        if url:
                            f.write(f"{title}: {url}\n")
                            count += 1
                        
                        for att in item.get("attachments", []):
                            att_url = att.get("url", "")
                            if att_url:
                                f.write(f"  └─ {att.get('name', 'file')}: {att_url}\n")
                                count += 1

            page += 1
            await asyncio.sleep(0.3)

        except Exception as e:
            LOGGER.error(f"Extract error: {e}")
            break

    return count


# ====================== MAIN CONVERSATION HANDLER ======================
@app.on_message(
    filters.text
    & filters.private
    & ~filters.command(["start", "myplan", "add_premium", "remove_premium",
                       "chk_premium", "cancel", "help"])
)
async def handle_conversation(client, message):
    """Route text messages based on user state."""
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
            await handle_batch_select_login(client, message, text)
        elif state == AWAITING_SUBJECTS:
            await handle_subjects(client, message, text)
        elif state == AWAITING_KEYWORD:
            await handle_keyword(client, message, text)
        elif state == AWAITING_BATCH_SELECT:
            await handle_batch_select_nologin(client, message, text)
        elif state == AWAITING_SUBJECTS_NL:
            await handle_subjects_nologin(client, message, text)
        elif state == AWAITING_NL_TOKEN:
            # Handle manual token input for without login
            universal_token = _get_working_token()
            if universal_token:
                user_data[user_id] = {
                    "state": AWAITING_KEYWORD,
                    "nl_token": universal_token
                }
                await message.reply_text("✅ Token configured! Now send a keyword to search.")
            else:
                await message.reply_text("❌ No universal token configured.")
                user_data.pop(user_id, None)

    except Exception as e:
        LOGGER.error(f"Conversation error: {e}")
        await message.reply_text(f"❌ Error: {str(e)[:100]}\n\nSend /start to try again.")
        user_data.pop(user_id, None)
