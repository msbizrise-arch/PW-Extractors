"""
PW (Physics Wallah) Extraction Module - FINAL FIXED
Based on databasepw.py reference
All OTP, Token, Without Login working
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

# ====================== CONVERSATION STATES ======================
AWAITING_PHONE = "awaiting_phone"
AWAITING_OTP = "awaiting_otp"
AWAITING_TOKEN = "awaiting_token"
AWAITING_BATCH = "awaiting_batch"
AWAITING_SUBJECTS = "awaiting_subjects"
AWAITING_KEYWORD = "awaiting_keyword"
AWAITING_BATCH_SELECT = "awaiting_batch_select"
AWAITING_SUBJECTS_NL = "awaiting_subjects_nl"

# User data store
user_data = {}


# ====================== HELPER FUNCTIONS (databasepw.py ke hisaab se) ======================
def _generate_randomid():
    """Generate randomid in format: 16 hex chars (databasepw.py style)"""
    return ''.join(random.choices('0123456789abcdef', k=16))


def _get_working_token():
    """Return the universal token from env if set"""
    return PW_UNIVERSAL_TOKEN.strip() if PW_UNIVERSAL_TOKEN else ""


# ====================== JWT FUNCTIONS (databasepw.py se exact) ======================
def decode_jwt(token: str) -> dict | None:
    """JWT token ka payload decode karo."""
    try:
        parts = token.strip().split('.')
        if len(parts) != 3:
            return None
        payload_b64 = parts[1].replace('-', '+').replace('_', '/')
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += '=' * padding
        payload_json = base64.b64decode(payload_b64).decode('utf-8')
        return json.loads(payload_json)
    except Exception as e:
        LOGGER.error(f"JWT decode error: {e}")
        return None


def is_token_valid(token: str) -> bool:
    """Check karo token valid hai ya expired."""
    payload = decode_jwt(token)
    if not payload:
        return False
    exp = payload.get('exp', 0)
    return int(time.time()) < exp


def get_token_info(token: str) -> dict:
    """Token se user ki info nikalo."""
    payload = decode_jwt(token)
    if not payload:
        return {}
    u = payload.get('data', {})
    exp = payload.get('exp', 0)
    days_left = max(0, (exp - int(time.time())) // 86400) if exp else 0
    return {
        "user_id": u.get('_id', ''),
        "name": f"{u.get('firstName', '')} {u.get('lastName', '')}".strip(),
        "mobile": u.get('username', ''),
        "email": u.get('email', ''),
        "expires_at": exp,
        "expires_str": time.strftime('%d %b %Y', time.localtime(exp)) if exp else 'Unknown',
        "days_left": days_left,
        "is_valid": is_token_valid(token),
    }


# ====================== PROXY SYSTEM (databasepw.py se exact) ======================
def try_proxies_for_token(phone: str, otp: str) -> str | None:
    """Sab proxies try karo agar direct fail ho."""
    tok_url = f"{PW_BASE_URL}/v3/oauth/token"
    body = json.dumps({
        "username": phone,
        "otp": otp,
        "client_id": "system-admin",
        "client_secret": PW_CLIENT_SECRET,
        "grant_type": "password",
        "organizationId": PW_ORG_ID,
        "latitude": 0,
        "longitude": 0,
    })
    proxy_urls = [
        f"https://corsproxy.io/?{quote(tok_url)}",
        f"https://api.allorigins.win/raw?url={quote(tok_url)}",
        f"https://thingproxy.freeboard.io/fetch/{tok_url}",
        f"https://api.codetabs.com/v1/proxy/?quest={quote(tok_url)}",
    ]
    for proxy_url in proxy_urls:
        try:
            r = requests.post(proxy_url, data=body,
                              headers={"Content-Type": "application/json"}, timeout=14)
            data = r.json()
            if "contents" in data:
                data = json.loads(data["contents"])
            if data.get("data", {}).get("access_token"):
                return data["data"]["access_token"]
        except Exception:
            continue
    return None


# ====================== CANCEL HANDLER ======================
@app.on_message(filters.command("cancel") & filters.private)
async def cancel_cmd(client, message):
    user_id = message.from_user.id
    if user_id in user_data:
        user_data.pop(user_id, None)
        await message.reply_text("❌ **Cancelled!**\n\nSend /start to begin again.")
    else:
        await message.reply_text("No active operation to cancel.")


# ====================== OTP HANDLERS (databasepw.py exact logic) ======================
async def handle_phone(client, message, phone):
    """Handle phone number input — databasepw.py style OTP sending"""
    user_id = message.from_user.id
    
    phone = phone.replace("+91", "").replace(" ", "").replace("-", "")
    if not phone.isdigit() or len(phone) != 10:
        await message.reply_text("❌ Invalid number. Send **10-digit mobile number**.")
        return

    status = await message.reply_text("📤 Sending OTP...")

    # PRIMARY ENDPOINT: v1 with smsType=0 (databasepw.py ke hisaab se)
    try:
        url = f"{PW_BASE_URL}/v1/users/get-otp?smsType=0"
        body = {
            "username": phone,
            "countryCode": "+91",
            "organizationId": PW_ORG_ID
        }
        headers = {
            "Content-Type": "application/json",
            "Client-Id": PW_ORG_ID,
            "Client-Type": "WEB",
            "Client-Version": "2.6.12",
            "Integration-With": "Origin",
        }
        
        resp = requests.post(url, json=body, headers=headers, timeout=8)
        LOGGER.info(f"OTP primary response: {resp.status_code}")
        
        if resp.status_code == 200:
            user_data[user_id] = {
                "state": AWAITING_OTP,
                "phone": phone
            }
            await status.edit_text(
                "✅ **OTP sent!**\n\n"
                "Send the **6-digit OTP** you received.\n"
                "Send /cancel to abort."
            )
            return
        elif resp.status_code == 429:
            await status.edit_text(
                "⚠️ **Rate Limited!**\n\n"
                "Too many requests. Wait 2-3 minutes and try again."
            )
            return
    except Exception as e:
        LOGGER.error(f"Primary OTP error: {e}")
        # Error aaye toh bhi proceed - OTP server-side gaya hoga

    # FALLBACK: Mobile headers try karo
    try:
        url2 = f"{PW_BASE_URL}/v1/users/get-otp"
        body2 = {
            "username": phone,
            "countryCode": "+91",
            "organizationId": PW_ORG_ID
        }
        headers2 = {
            "Content-Type": "application/json",
            "client-id": PW_ORG_ID,
            "client-type": "MOBILE",
            "client-version": "12.84",
            "randomid": _generate_randomid(),
        }
        
        resp2 = requests.post(url2, json=body2, headers=headers2, timeout=8)
        if resp2.status_code == 200:
            user_data[user_id] = {
                "state": AWAITING_OTP,
                "phone": phone
            }
            await status.edit_text("✅ **OTP sent via alternate method!**\n\nSend OTP now.")
            return
    except Exception as e:
        LOGGER.error(f"Fallback OTP error: {e}")

    # Agar sab fail ho
    await status.edit_text(
        "❌ **Failed to send OTP**\n\n"
        "Try:\n"
        "1. Wait 5 minutes\n"
        "2. Use Direct Token\n"
        "3. Use Without Login"
    )


async def handle_otp(client, message, otp):
    """Handle OTP verification — databasepw.py style token generation"""
    user_id = message.from_user.id
    user_info = user_data.get(user_id, {})
    phone = user_info.get("phone", "")
    
    otp = otp.strip().replace(" ", "")
    if not otp.isdigit() or len(otp) < 4:
        await message.reply_text("❌ Invalid OTP.")
        return

    status = await message.reply_text("🔐 Verifying OTP...")

    # Token generation (databasepw.py exact)
    url = f"{PW_BASE_URL}/v3/oauth/token"
    body = {
        "username": phone,
        "otp": otp,
        "client_id": "system-admin",
        "client_secret": PW_CLIENT_SECRET,
        "grant_type": "password",
        "organizationId": PW_ORG_ID,
        "latitude": 0,
        "longitude": 0,
    }
    headers = {
        "Content-Type": "application/json",
        "Client-Id": PW_ORG_ID,
        "Client-Type": "WEB",
        "Client-Version": "2.6.12",
        "Integration-With": "",
        "Randomid": _generate_randomid(),
        "Referer": "https://www.pw.live/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    }

    token = None
    
    # Direct call try karo
    try:
        resp = requests.post(url, json=body, headers=headers, timeout=14)
        data = resp.json()
        if data.get("data", {}).get("access_token"):
            token = data["data"]["access_token"]
    except Exception as e:
        LOGGER.error(f"Direct token error: {e}")

    # Proxy fallback
    if not token:
        token = try_proxies_for_token(phone, otp)

    if token:
        user_data[user_id]["token"] = token
        info = get_token_info(token)
        status_text = "✅ Valid" if info.get('is_valid') else "⚠️ Expired"
        
        await status.edit_text(
            f"✅ **Login Successful!**\n"
            f"👤 {info.get('name', 'User')}\n"
            f"🔐 {status_text}\n\n"
            f"Fetching batches..."
        )
        await show_batches_login(client, message, token)
    else:
        await status.edit_text(
            "❌ **OTP Verification Failed**\n\n"
            "Invalid OTP or server issue.\n"
            "Send /start to try again."
        )
        user_data.pop(user_id, None)


# ====================== TOKEN HANDLER ======================
async def handle_token_input(client, message, token):
    """Handle direct token input"""
    user_id = message.from_user.id

    token = token.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()

    status = await message.reply_text("🔍 Validating token...")
    
    info = get_token_info(token)
    if info.get('name'):
        if info.get('is_valid'):
            await status.edit_text("✅ **Token valid!** Fetching batches...")
        else:
            await status.edit_text("⚠️ **Token expired** - will try anyway...")
    else:
        await status.edit_text("⚠️ Trying token...")

    user_data[user_id] = {"token": token}
    await show_batches_login(client, message, token)


# ====================== BATCH FETCHING ======================
async def show_batches_login(client, message, token):
    """Fetch and display user's batches"""
    user_id = message.chat.id
    batches = []
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Client-Id": PW_ORG_ID,
        "Client-Type": "WEB",
        "Client-Version": "2.6.12",
        "Content-Type": "application/json",
    }

    # Try my-batches endpoint
    try:
        resp = requests.get(
            f"{PW_BASE_URL}/v3/batches/my-batches",
            headers=headers,
            timeout=15,
        )
        if resp.status_code == 200:
            batches = resp.json().get("data", [])
    except Exception as e:
        LOGGER.error(f"Batch fetch error: {e}")

    if not batches:
        await message.reply_text(
            "❌ **No batches found**\n\n"
            "Try Without Login feature instead."
        )
        user_data.pop(user_id, None)
        return

    text = f"**📚 Found {len(batches)} Batches:**\n\n"
    for i, b in enumerate(batches[:20], 1):
        text += f"`{i}.` **{b.get('name', 'Unknown')}**\n"

    text += f"\n**Send a number (1-{min(20, len(batches))})**\n/cancel to abort"

    user_data[user_id].update({
        "batches": batches[:20],
        "state": AWAITING_BATCH
    })
    await message.reply_text(text)


# ====================== WITHOUT LOGIN ======================
async def handle_keyword(client, message, keyword):
    """Search batches with universal token"""
    user_id = message.from_user.id
    
    universal_token = _get_working_token()
    if not universal_token:
        await message.reply_text(
            "❌ **Universal token not configured**\n\n"
            "Contact admin to set PW_UNIVERSAL_TOKEN"
        )
        return

    status = await message.reply_text(f"🔍 Searching for **'{keyword}'**...")

    headers = {
        "Authorization": f"Bearer {universal_token}",
        "Client-Id": PW_ORG_ID,
        "Client-Type": "WEB",
        "Client-Version": "2.6.12",
    }

    all_results = []
    page = 1

    try:
        while page <= 5:
            resp = requests.get(
                f"{PW_BASE_URL}/v3/batches",
                params={
                    "organizationId": PW_ORG_ID,
                    "page": page,
                    "limit": 50,
                    "search": keyword
                },
                headers=headers,
                timeout=15,
            )
            
            if resp.status_code != 200:
                break
                
            data = resp.json().get("data", [])
            if not data:
                break
                
            all_results.extend(data)
            
            if len(data) < 50:
                break
            page += 1
            await asyncio.sleep(0.5)

    except Exception as e:
        LOGGER.error(f"Search error: {e}")

    if not all_results:
        await status.edit_text(f"❌ No batches found for '{keyword}'")
        return

    text = f"**🔍 Found {len(all_results)} batches:**\n\n"
    for i, b in enumerate(all_results[:20], 1):
        text += f"`{i}.` **{b.get('name', 'Unknown')}**\n"

    text += f"\n**Send a number (1-{min(20, len(all_results))})**"

    user_data[user_id] = {
        "state": AWAITING_BATCH_SELECT,
        "nl_batches": all_results[:20],
        "nl_token": universal_token,
    }
    await status.edit_text(text)


# ====================== BATCH SELECTION ======================
async def handle_batch_select_login(client, message, choice):
    user_id = message.from_user.id
    user_info = user_data.get(user_id, {})
    batches = user_info.get("batches", [])
    token = user_info.get("token", "")

    if not choice.isdigit() or not (1 <= int(choice) <= len(batches)):
        await message.reply_text(f"❌ Send number between 1-{len(batches)}")
        return

    selected = batches[int(choice) - 1]
    batch_id = selected.get("_id")
    batch_name = selected.get("name")

    await fetch_subjects(client, message, batch_id, batch_name, token, user_id, AWAITING_SUBJECTS)


async def handle_batch_select_nologin(client, message, choice):
    user_id = message.from_user.id
    user_info = user_data.get(user_id, {})
    batches = user_info.get("nl_batches", [])
    token = user_info.get("nl_token", "")

    if not choice.isdigit() or not (1 <= int(choice) <= len(batches)):
        await message.reply_text(f"❌ Send number between 1-{len(batches)}")
        return

    selected = batches[int(choice) - 1]
    batch_id = selected.get("_id")
    batch_name = selected.get("name")

    await fetch_subjects(client, message, batch_id, batch_name, token, user_id, AWAITING_SUBJECTS_NL)


async def fetch_subjects(client, message, batch_id, batch_name, token, user_id, next_state):
    status = await message.reply_text("⏳ Fetching subjects...")

    headers = {
        "Authorization": f"Bearer {token}",
        "Client-Id": PW_ORG_ID,
        "Client-Type": "WEB",
        "Client-Version": "2.6.12",
    }

    subjects = []
    try:
        resp = requests.get(
            f"{PW_BASE_URL}/v3/batches/{batch_id}/details",
            headers=headers,
            timeout=15,
        )
        if resp.status_code == 200:
            subjects = resp.json().get("data", {}).get("subjects", [])
    except Exception as e:
        LOGGER.error(f"Subject fetch error: {e}")

    if not subjects:
        await status.edit_text("❌ No subjects found")
        user_data.pop(user_id, None)
        return

    text = f"**📖 Subjects in {batch_name}:**\n\n"
    for i, s in enumerate(subjects, 1):
        text += f"`{i}.` **{s.get('subject', 'Unknown')}**\n"

    text += "\n**Send numbers (e.g., `1 2 3` or `all`)**"

    user_data[user_id].update({
        "batch_id": batch_id,
        "batch_name": batch_name,
        "subjects": subjects,
        "state": next_state,
    })
    await status.edit_text(text)


# ====================== SUBJECT SELECTION ======================
async def handle_subjects(client, message, subject_text):
    user_id = message.from_user.id
    user_info = user_data.get(user_id, {})
    token = user_info.get("token", "")
    batch_id = user_info.get("batch_id")
    batch_name = user_info.get("batch_name")
    subjects = user_info.get("subjects", [])

    subject_ids = parse_subject_selection(subject_text, subjects)
    if not subject_ids:
        await message.reply_text("❌ No valid subjects selected")
        return

    headers = {
        "Authorization": f"Bearer {token}",
        "Client-Id": PW_ORG_ID,
        "Client-Type": "WEB",
        "Client-Version": "2.6.12",
    }
    
    user_data.pop(user_id, None)
    await extract_content(client, message, headers, batch_id, batch_name, subjects, subject_ids)


async def handle_subjects_nologin(client, message, subject_text):
    user_id = message.from_user.id
    user_info = user_data.get(user_id, {})
    token = user_info.get("nl_token", "")
    batch_id = user_info.get("batch_id")
    batch_name = user_info.get("batch_name")
    subjects = user_info.get("subjects", [])

    subject_ids = parse_subject_selection(subject_text, subjects)
    if not subject_ids:
        await message.reply_text("❌ No valid subjects selected")
        return

    headers = {
        "Authorization": f"Bearer {token}",
        "Client-Id": PW_ORG_ID,
        "Client-Type": "WEB",
        "Client-Version": "2.6.12",
    }
    
    user_data.pop(user_id, None)
    await extract_content(client, message, headers, batch_id, batch_name, subjects, subject_ids)


def parse_subject_selection(text, subjects):
    if text.strip().lower() == "all":
        return [s.get("_id", s.get("subjectId")) for s in subjects if s.get("_id") or s.get("subjectId")]
    
    ids = []
    for part in text.replace(",", " ").split():
        if part.isdigit():
            idx = int(part) - 1
            if 0 <= idx < len(subjects):
                sid = subjects[idx].get("_id", subjects[idx].get("subjectId"))
                if sid:
                    ids.append(sid)
    return ids


# ====================== EXTRACTION ENGINE ======================
async def extract_content(client, message, headers, batch_id, batch_name, subjects, subject_ids):
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

        await message.reply_text("🚀 Extraction started...")

        for idx, sid in enumerate(subject_ids):
            sub_name = "Unknown"
            for s in subjects:
                if s.get("_id") == sid or s.get("subjectId") == sid:
                    sub_name = s.get("subject", "Unknown")
                    break

            # Videos
            vcount = await extract_type(filename, headers, batch_id, sid, sub_name, "videos", "📹 VIDEOS")
            total_videos += vcount

            # Notes
            ncount = await extract_type(filename, headers, batch_id, sid, sub_name, "notes", "📄 NOTES")
            total_notes += ncount

            # DPPs
            dcount = await extract_type(filename, headers, batch_id, sid, sub_name, "DppNotes", "📝 DPPs")
            total_notes += dcount

        if total_videos + total_notes == 0:
            await message.reply_text("⚠️ No content found")
            return

        caption = f"✅ **Complete!**\n📹 Videos: {total_videos}\n📄 Notes: {total_notes}"
        await client.send_document(message.chat.id, filename, caption=caption)

    except Exception as e:
        LOGGER.error(f"Extraction error: {e}")
        await message.reply_text(f"❌ Error: {str(e)[:100]}")
    finally:
        if os.path.exists(filename):
            os.remove(filename)


async def extract_type(filename, headers, batch_id, subject_id, subject_name, content_type, header_text):
    count = 0
    page = 1

    with open(filename, "a", encoding="utf-8") as f:
        f.write(f"\n{header_text} - {subject_name}\n")
        f.write("-" * 40 + "\n")

    while page <= 10:
        try:
            resp = requests.get(
                f"{PW_BASE_URL}/v3/batches/{batch_id}/subject/{subject_id}/contents",
                params={"page": page, "contentType": content_type},
                headers=headers,
                timeout=15,
            )
            if resp.status_code != 200:
                break

            items = resp.json().get("data", [])
            if not items:
                break

            with open(filename, "a", encoding="utf-8") as f:
                for item in items:
                    title = item.get("topic", item.get("title", "Untitled"))
                    
                    if content_type in ("videos", "DppVideos"):
                        url = item.get("url") or item.get("videoDetails", {}).get("videoUrl")
                        if url:
                            f.write(f"{title}: {url}\n")
                            count += 1
                    else:
                        url = item.get("url") or item.get("pdfUrl") or item.get("fileUrl")
                        if url:
                            f.write(f"{title}: {url}\n")
                            count += 1

            page += 1
            await asyncio.sleep(0.3)
        except Exception:
            break

    return count


# ====================== MAIN HANDLER ======================
@app.on_message(filters.text & filters.private & ~filters.command(["start", "myplan", "add_premium", "remove_premium", "chk_premium", "cancel", "help"]))
async def handle_conversation(client, message):
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
    except Exception as e:
        LOGGER.error(f"Conversation error: {e}")
        await message.reply_text(f"❌ Error\n\nSend /start to try again.")
        user_data.pop(user_id, None)
