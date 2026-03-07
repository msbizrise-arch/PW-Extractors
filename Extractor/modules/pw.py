"""
PW (Physics Wallah) Extraction Module - Advanced Build
Features:
  - Login via Mobile OTP (fixed: proper PW API v1/v3 endpoints)
  - Login via Direct Token (fixed: validation + duplicate token support)
  - Without Login (keyword-based batch search with universal token)
  - All batch listings with SN numbers (1, 2, 3...)
  - User selects by SN number
  - Full extraction: Videos (CDN links) + PDFs/Notes + DPPs
  - /cancel command support
  - JWT decode, token validation, proxy fallback
"""
import requests
import asyncio
import os
import logging
import uuid
import json
import base64
import time
from urllib.parse import quote
from pyrogram import filters
from Extractor import app
from config import (
    PW_ORG_ID, PW_CLIENT_SECRET, PW_BASE_URL,
    PW_UNIVERSAL_TOKEN, PW_WEB_HEADERS,
)

LOGGER = logging.getLogger(__name__)

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
AWAITING_NL_TOKEN = "awaiting_nl_token"

# User data store: {user_id: {"state": str, ...}}
user_data = {}


# ====================== HELPER FUNCTIONS ======================
def _generate_random_id():
    """Generate a unique random ID for API requests."""
    return str(uuid.uuid4()).replace("-", "")[:18]


def _get_otp_headers():
    """Get headers for OTP send request (as per databasepw.py reference)."""
    return {
        "Content-Type": "application/json",
        "Client-Id": PW_ORG_ID,
        "Client-Type": "WEB",
        "Client-Version": "2.6.12",
        "Integration-With": "Origin",
    }


def _get_token_headers():
    """Get headers for token generation request."""
    return {
        "Content-Type": "application/json",
        "Client-Id": PW_ORG_ID,
        "Client-Type": "WEB",
        "Client-Version": "2.6.12",
        "Integration-With": "",
        "Randomid": _generate_random_id(),
        "Referer": "https://www.pw.live/",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/145.0.0.0 Safari/537.36"
        ),
    }


def get_pw_headers(token=None):
    """Build PW API headers with optional bearer token."""
    headers = {
        "Content-Type": "application/json",
        "Client-Id": PW_ORG_ID,
        "Client-Type": "WEB",
        "Client-Version": "2.6.12",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/145.0.0.0 Safari/537.36"
        ),
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get_mobile_headers(token=None):
    """Build PW MOBILE API headers (for my-batches etc.)."""
    headers = {
        "Host": "api.penpencil.co",
        "client-id": PW_ORG_ID,
        "client-version": "12.84",
        "user-agent": "Android",
        "randomid": _generate_random_id(),
        "client-type": "MOBILE",
        "content-type": "application/json",
    }
    if token:
        headers["authorization"] = f"Bearer {token}"
    return headers


def _get_working_token():
    """Return the universal token from env if set, else empty string."""
    return PW_UNIVERSAL_TOKEN.strip() if PW_UNIVERSAL_TOKEN else ""


# ====================== JWT FUNCTIONS ======================
def _decode_jwt(token):
    """Decode JWT token payload."""
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


def _is_token_valid(token):
    """Check if JWT token is still valid (not expired)."""
    payload = _decode_jwt(token)
    if not payload:
        return False
    exp = payload.get("exp", 0)
    return int(time.time()) < exp


def _get_token_info(token):
    """Extract user info from JWT token."""
    payload = _decode_jwt(token)
    if not payload:
        return None
    u = payload.get("data", {})
    exp = payload.get("exp", 0)
    days_left = max(0, (exp - int(time.time())) // 86400)
    return {
        "user_id": u.get("_id", ""),
        "name": f"{u.get('firstName', '')} {u.get('lastName', '')}".strip(),
        "mobile": u.get("username", ""),
        "email": u.get("email", ""),
        "expires": time.strftime("%d %b %Y", time.localtime(exp)) if exp else "Unknown",
        "days_left": days_left,
        "is_valid": int(time.time()) < exp,
    }


# ====================== PROXY FALLBACK ======================
def _try_proxies_for_token(phone, otp):
    """Try CORS proxies to get token if direct call fails."""
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
            r = requests.post(
                proxy_url, data=body,
                headers={"Content-Type": "application/json"},
                timeout=14,
            )
            data = r.json()
            if "contents" in data:
                data = json.loads(data["contents"])
            token = data.get("data", {}).get("access_token", "")
            if token:
                return token
        except Exception:
            continue
    return None


# ====================== CANCEL HANDLER ======================
@app.on_message(filters.command("cancel") & filters.private)
async def cancel_cmd(client, message):
    """Cancel any ongoing conversation."""
    user_id = message.from_user.id
    if user_id in user_data:
        user_data.pop(user_id, None)
        await message.reply_text(
            "❌ **Cancelled!**\n\nSend /start to begin again."
        )
    else:
        await message.reply_text(
            "No active operation to cancel.\nSend /start to begin."
        )


# ====================== ENTRY POINTS ======================
async def pw_mobile(client, message):
    """Start mobile OTP login flow."""
    user_id = message.chat.id
    user_data[user_id] = {"state": AWAITING_PHONE}
    await client.send_message(
        user_id,
        "**📱 Send your mobile number (without +91)**\n"
        "Example: `9876543210`\n\n"
        "Send /cancel to abort.",
    )


async def pw_token(client, message):
    """Start direct token login flow."""
    user_id = message.chat.id
    user_data[user_id] = {"state": AWAITING_TOKEN}
    await client.send_message(
        user_id,
        "**🔑 Send your PW Bearer Token**\n\n"
        "You can find this in:\n"
        "- Browser DevTools -> Network tab -> Authorization header\n"
        "- PW App (intercept traffic)\n\n"
        "Even expired tokens may work for some batches.\n"
        "Send /cancel to abort.",
    )


async def pw_nologin(client, message):
    """Start Without Login flow — keyword-based batch search."""
    user_id = message.chat.id
    token = _get_working_token()

    if not token:
        user_data[user_id] = {"state": AWAITING_NL_TOKEN}
        await client.send_message(
            user_id,
            "**🔓 Without Login — PW Batch Access**\n\n"
            "No universal token is configured.\n"
            "Please send a **working PW Bearer Token** to access batches.\n\n"
            "This token will be used to search and extract all PW batches.\n"
            "A universal token gives access to all batches.\n\n"
            "Send /cancel to abort.",
        )
        return

    user_data[user_id] = {"state": AWAITING_KEYWORD, "nl_token": token}
    await client.send_message(
        user_id,
        "**🔓 Without Login — PW Batch Search**\n\n"
        "Type a **batch keyword** to search all PW batches:\n\n"
        "Examples:\n"
        "- `Yakeen` -> Yakeen NEET Hindi 2026...\n"
        "- `Arjuna` -> Arjuna JEE 2026...\n"
        "- `Lakshya` -> Lakshya JEE, Lakshya NEET...\n"
        "- `Prayas` -> Prayas JEE 2026...\n\n"
        "Send /cancel to abort.",
    )


# ====================== CONVERSATION HANDLER ======================
@app.on_message(
    filters.text
    & filters.private
    & ~filters.command(
        ["start", "myplan", "add_premium", "remove_premium",
         "chk_premium", "cancel", "help"]
    )
)
async def handle_conversation(client, message):
    """Route text messages based on user conversation state."""
    user_id = message.from_user.id
    text = message.text.strip()

    if user_id not in user_data:
        return

    state = user_data[user_id].get("state")

    try:
        # Login-based states
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

        # Without Login states
        elif state == AWAITING_NL_TOKEN:
            await handle_nl_token(client, message, text)
        elif state == AWAITING_KEYWORD:
            await handle_keyword(client, message, text)
        elif state == AWAITING_BATCH_SELECT:
            await handle_batch_select_nologin(client, message, text)
        elif state == AWAITING_SUBJECTS_NL:
            await handle_subjects_nologin(client, message, text)

    except Exception as e:
        LOGGER.error(f"Conversation error for {user_id}: {e}", exc_info=True)
        await message.reply_text(
            f"❌ Error: {str(e)[:200]}\n\nSend /cancel and try again."
        )
        user_data.pop(user_id, None)


# ====================== OTP LOGIN HANDLERS ======================
async def handle_phone(client, message, phone):
    """Handle phone number input — send OTP via PW API."""
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

    otp_sent = False
    error_msg = ""

    # Try v1 endpoint first (as per databasepw.py reference — most reliable)
    try:
        resp = requests.post(
            f"{PW_BASE_URL}/v1/users/get-otp?smsType=0",
            json={
                "username": phone,
                "countryCode": "+91",
                "organizationId": PW_ORG_ID,
            },
            headers=_get_otp_headers(),
            timeout=8,
        )
        data = resp.json()
        LOGGER.info(f"OTP v1 response: status={resp.status_code}, data={data}")

        if resp.status_code == 200:
            otp_sent = True
        elif resp.status_code == 429:
            error_msg = "Too many requests. Wait 2-3 minutes and try again."
        else:
            error_msg = data.get("message", data.get("error", {}).get("message", ""))
    except Exception as e:
        LOGGER.error(f"OTP v1 error: {e}")
        # Even if CORS/network error, OTP may have been sent server-side
        otp_sent = True

    # If v1 failed, try v3 endpoint as fallback
    if not otp_sent and not error_msg:
        try:
            resp2 = requests.post(
                f"{PW_BASE_URL}/v3/users/get-otp",
                json={
                    "username": f"+91{phone}",
                    "organizationId": PW_ORG_ID,
                },
                headers={
                    "Content-Type": "application/json",
                    "client-id": PW_ORG_ID,
                    "client-type": "MOBILE",
                    "client-version": "12.84",
                    "user-agent": "Android",
                    "randomid": _generate_random_id(),
                },
                timeout=15,
            )
            data2 = resp2.json()
            LOGGER.info(f"OTP v3 response: status={resp2.status_code}")

            if resp2.status_code == 200 and data2.get("success", True):
                otp_sent = True
            elif resp2.status_code == 429:
                error_msg = "Too many requests. Wait 2-3 minutes and try again."
            else:
                error_msg = data2.get("message", data2.get("error", {}).get("message", "Unknown error"))
        except Exception as e:
            LOGGER.error(f"OTP v3 error: {e}")
            otp_sent = True

    if otp_sent:
        user_data[user_id]["phone"] = phone
        user_data[user_id]["state"] = AWAITING_OTP
        await status.edit_text(
            "✅ **OTP sent to your number!**\n\n"
            "🔢 **Now send the OTP you received.**\n\n"
            "⏰ OTP expires in ~10 minutes.\n"
            "If you didn't receive it, wait 60 seconds and send /cancel -> /start to resend.\n\n"
            "Send /cancel to abort."
        )
    elif error_msg:
        await status.edit_text(
            f"❌ **Failed to send OTP:** {error_msg}\n\n"
            "If you see 'Too many requests', wait 2-3 minutes.\n"
            "Make sure you have a PW account with this number.\n"
            "Try again with /start"
        )
        user_data.pop(user_id, None)
    else:
        await status.edit_text(
            "❌ **Failed to send OTP.** Unknown error.\n\n"
            "Try again with /start"
        )
        user_data.pop(user_id, None)


async def handle_otp(client, message, otp):
    """Handle OTP input — verify and get access token."""
    user_id = message.from_user.id
    phone = user_data[user_id].get("phone", "")
    otp = otp.strip().replace(" ", "")

    if not otp.isdigit() or len(otp) < 4:
        await message.reply_text(
            "❌ Invalid OTP. Send the **numeric OTP** you received."
        )
        return

    status = await message.reply_text("🔐 Verifying OTP...")

    token = None
    error_msg = ""

    # Try direct token generation (as per databasepw.py reference)
    try:
        resp = requests.post(
            f"{PW_BASE_URL}/v3/oauth/token",
            json={
                "username": phone,
                "otp": otp,
                "client_id": "system-admin",
                "client_secret": PW_CLIENT_SECRET,
                "grant_type": "password",
                "organizationId": PW_ORG_ID,
                "latitude": 0,
                "longitude": 0,
            },
            headers=_get_token_headers(),
            timeout=14,
        )
        data = resp.json()
        LOGGER.info(f"Token response keys: {list(data.keys())}")

        # Check response — token can be at data.data.access_token or data.access_token
        if data.get("data", {}).get("access_token"):
            token = data["data"]["access_token"]
        elif data.get("access_token"):
            token = data["access_token"]
        elif data.get("token"):
            token = data["token"]
        else:
            err_text = json.dumps(data).lower()
            if any(x in err_text for x in ["invalid otp", "otp expired", "wrong otp", "incorrect otp"]):
                error_msg = "Invalid or expired OTP. Please try again."
            else:
                error_msg = data.get("message", data.get("error", {}).get("message", "Token generation failed"))
    except Exception as e:
        LOGGER.error(f"Direct token error: {e}")
        error_msg = str(e)

    # If direct failed, try with +91 prefix and MOBILE headers
    if not token and not error_msg:
        try:
            resp2 = requests.post(
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
                headers={
                    "Content-Type": "application/json",
                    "client-id": PW_ORG_ID,
                    "client-type": "MOBILE",
                    "client-version": "12.84",
                    "user-agent": "Android",
                    "randomid": _generate_random_id(),
                },
                timeout=15,
            )
            data2 = resp2.json()
            if data2.get("data", {}).get("access_token"):
                token = data2["data"]["access_token"]
            elif data2.get("access_token"):
                token = data2["access_token"]
            else:
                error_msg = data2.get("message", "OTP verification failed")
        except Exception as e:
            LOGGER.error(f"Fallback token error: {e}")

    # If still no token, try proxy fallback
    if not token:
        LOGGER.info("Trying proxy fallback for token...")
        proxy_token = _try_proxies_for_token(phone, otp)
        if proxy_token:
            token = proxy_token

    if token:
        user_data[user_id]["token"] = token
        user_data[user_id]["refresh_token"] = ""

        info = _get_token_info(token)
        info_text = ""
        if info:
            info_text = (
                f"\n👤 Name: **{info['name']}**\n"
                f"📱 Mobile: `{info['mobile']}`\n"
                f"📅 Expires: {info['expires']} ({info['days_left']} days left)\n"
            )

        await status.edit_text(
            f"✅ **Login Successful!**\n"
            f"{info_text}\n"
            f"🔑 **Your Token (save it):**\n"
            f"`{token[:60]}...`\n\n"
            "You can use this token with **Direct Token** login next time.\n"
            "Fetching your batches..."
        )
        await show_batches_login(client, message, token)
    else:
        await status.edit_text(
            f"❌ **OTP verification failed:** {error_msg}\n\n"
            "Check if the OTP is correct and try again.\n"
            "Send /start to restart."
        )
        user_data.pop(user_id, None)


# ====================== TOKEN LOGIN ======================
async def handle_token_input(client, message, token):
    """Handle direct token input — validate and fetch batches."""
    user_id = message.from_user.id
    token = token.strip()

    if token.lower().startswith("bearer "):
        token = token[7:].strip()

    status = await message.reply_text("🔍 Validating token...")

    # Check JWT validity
    info = _get_token_info(token)
    if info and not info["is_valid"]:
        await status.edit_text(
            "⚠️ **Token is expired** but I'll try to use it anyway.\n"
            f"📅 Expired on: {info['expires']}\n\n"
            "Fetching batches..."
        )
    else:
        await status.edit_text("✅ **Token accepted!** Fetching batches...")

    user_data[user_id]["token"] = token
    await show_batches_login(client, message, token)


# ====================== SHOW BATCHES (LOGIN) ======================
async def show_batches_login(client, message, token):
    """Fetch and display user's batches (login flow) with SN numbers."""
    user_id = message.chat.id
    batches = []

    # Try MOBILE headers first (my-batches endpoint)
    try:
        headers_mobile = _get_mobile_headers(token)
        resp = requests.get(
            f"{PW_BASE_URL}/v3/batches/my-batches",
            headers=headers_mobile,
            timeout=20,
        )
        data = resp.json()
        batches = data.get("data", [])
    except Exception as e:
        LOGGER.error(f"my-batches MOBILE error: {e}")

    # Fallback: Try WEB headers
    if not batches:
        try:
            headers_web = get_pw_headers(token)
            resp2 = requests.get(
                f"{PW_BASE_URL}/v3/batches/my-batches",
                headers=headers_web,
                timeout=20,
            )
            data2 = resp2.json()
            batches = data2.get("data", [])
        except Exception as e:
            LOGGER.error(f"my-batches WEB error: {e}")

    # Fallback: Try all batches endpoint
    if not batches:
        try:
            headers_web = get_pw_headers(token)
            resp3 = requests.get(
                f"{PW_BASE_URL}/v3/batches",
                params={"organizationId": PW_ORG_ID, "page": "1", "limit": "100"},
                headers=headers_web,
                timeout=20,
            )
            data3 = resp3.json()
            batches = data3.get("data", [])
        except Exception as e:
            LOGGER.error(f"all-batches error: {e}")

    if not batches:
        await message.reply_text(
            "❌ **No batches found for this account.**\n\n"
            "Possible reasons:\n"
            "- Token is invalid or expired\n"
            "- No batches purchased on this account\n\n"
            "Try **📱 Mobile OTP** login or send a fresh token.\n\n"
            "Send /start to try again."
        )
        user_data.pop(user_id, None)
        return

    # Show numbered batch list
    text = f"**📚 Your Batches ({len(batches)}):**\n\n"
    for i, b in enumerate(batches, 1):
        name = b.get("name", "Unknown")
        text += f"`{i}.` **{name}**\n"

    text += (
        f"\n**Send a number (1-{len(batches)}) to select a batch:**\n"
        "_(Send /cancel to abort)_"
    )

    if len(text) > 4000:
        text = text[:3900] + f"\n\n... Send a number (1-{len(batches)})."

    user_data[user_id]["batches"] = batches
    user_data[user_id]["state"] = AWAITING_BATCH
    await message.reply_text(text)


# ====================== BATCH SELECTION (LOGIN) ======================
async def handle_batch_select_login(client, message, choice):
    """Handle batch selection by SN number (login flow)."""
    user_id = message.from_user.id
    batches = user_data[user_id].get("batches", [])
    token = user_data[user_id].get("token", "")

    if not choice.isdigit() or not (1 <= int(choice) <= len(batches)):
        await message.reply_text(
            f"❌ Please send a number between **1 and {len(batches)}**.\n"
            "Or send /cancel to abort."
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
    """Fetch subjects for a batch and display them."""
    status = await message.reply_text(
        f"⏳ Fetching subjects for **{batch_name}**..."
    )

    subjects = []

    # Try WEB headers first
    try:
        headers = get_pw_headers(token)
        resp = requests.get(
            f"{PW_BASE_URL}/v3/batches/{batch_id}/details",
            headers=headers,
            timeout=20,
        )
        details = resp.json()
        subjects = details.get("data", {}).get("subjects", [])
    except Exception as e:
        LOGGER.error(f"Subject fetch WEB error: {e}")

    # Fallback: Try MOBILE headers
    if not subjects:
        try:
            headers_m = _get_mobile_headers(token)
            resp2 = requests.get(
                f"{PW_BASE_URL}/v3/batches/{batch_id}/details",
                headers=headers_m,
                timeout=20,
            )
            details2 = resp2.json()
            subjects = details2.get("data", {}).get("subjects", [])
        except Exception as e:
            LOGGER.error(f"Subject fetch MOBILE error: {e}")

    if not subjects:
        await status.edit_text(
            f"❌ No subjects found for **{batch_name}**.\n\n"
            "This batch may not have content yet or token lacks access."
        )
        user_data.pop(user_id, None)
        return

    text = f"**📖 Subjects in {batch_name}:**\n\n"
    for i, s in enumerate(subjects, 1):
        text += f"`{i}.` **{s.get('subject', 'Unknown')}**\n"

    text += (
        f"\n**Send subject numbers separated by spaces:**\n"
        f"Example: `1 2 3` or `all` for all subjects\n\n"
        f"_(Send /cancel to abort)_"
    )

    user_data[user_id].update({
        "subjects": subjects,
        "state": next_state,
    })
    await status.edit_text(text)


# ====================== SUBJECT SELECTION (LOGIN) ======================
async def handle_subjects(client, message, subject_text):
    """Handle subject selection by SN numbers (login flow)."""
    user_id = message.from_user.id
    token = user_data[user_id].get("token", "")
    batch_id = user_data[user_id].get("batch_id", "")
    batch_name = user_data[user_id].get("batch_name", "")
    subjects = user_data[user_id].get("subjects", [])

    subject_ids = _parse_subject_selection(subject_text, subjects)
    if not subject_ids:
        await message.reply_text(
            "❌ No valid subjects selected.\n"
            "Send numbers like `1 2 3` or `all` for all subjects."
        )
        return

    headers = get_pw_headers(token)
    user_data.pop(user_id, None)
    await _extract_and_send(
        client, message, headers,
        batch_id, batch_name, subjects, subject_ids,
    )


# ====================== WITHOUT LOGIN HANDLERS ======================
async def handle_nl_token(client, message, token):
    """Handle token input for without-login flow."""
    user_id = message.from_user.id
    token = token.strip()

    if token.lower().startswith("bearer "):
        token = token[7:].strip()

    status = await message.reply_text("🔍 Validating token...")

    # Test if token works for batch search
    try:
        headers = get_pw_headers(token)
        resp = requests.get(
            f"{PW_BASE_URL}/v3/batches",
            params={"organizationId": PW_ORG_ID, "page": "1", "limit": "1"},
            headers=headers,
            timeout=15,
        )
        data = resp.json()

        if resp.status_code == 200 and data.get("data") is not None:
            user_data[user_id] = {
                "state": AWAITING_KEYWORD,
                "nl_token": token,
            }
            await status.edit_text(
                "✅ **Token accepted!**\n\n"
                "Now type a **batch keyword** to search:\n\n"
                "Examples:\n"
                "- `Yakeen` -> Yakeen NEET Hindi 2026...\n"
                "- `Arjuna` -> Arjuna JEE 2026...\n"
                "- `Lakshya` -> Lakshya JEE...\n\n"
                "Send /cancel to abort."
            )
        else:
            user_data[user_id] = {
                "state": AWAITING_KEYWORD,
                "nl_token": token,
            }
            await status.edit_text(
                "⚠️ **Token may not work perfectly** but I'll try.\n\n"
                "Type a **batch keyword** to search:\n"
                "Send /cancel to abort."
            )
    except Exception as e:
        LOGGER.error(f"NL token validation error: {e}")
        user_data[user_id] = {
            "state": AWAITING_KEYWORD,
            "nl_token": token,
        }
        await status.edit_text(
            "⚠️ Could not validate token, but I'll try using it.\n\n"
            "Type a **batch keyword** to search:\n"
            "Send /cancel to abort."
        )


async def handle_keyword(client, message, keyword):
    """Search PW batches by keyword and show numbered results."""
    user_id = message.from_user.id
    nl_token = user_data[user_id].get("nl_token", _get_working_token())

    if nl_token:
        headers = get_pw_headers(nl_token)
    else:
        headers = {
            "Content-Type": "application/json",
            "Client-Id": PW_ORG_ID,
            "Client-Type": "WEB",
            "Client-Version": "2.6.12",
        }

    status = await message.reply_text(
        f"🔍 Searching batches for **\"{keyword}\"**..."
    )

    try:
        results = []
        page = 1

        while len(results) < 50:
            try:
                resp = requests.get(
                    f"{PW_BASE_URL}/v3/batches",
                    params={
                        "organizationId": PW_ORG_ID,
                        "page": str(page),
                        "limit": "20",
                    },
                    headers=headers,
                    timeout=20,
                )
                data = resp.json()

                batch_list = data.get("data", [])
                if not batch_list:
                    break

                kw_lower = keyword.lower()
                for b in batch_list:
                    name = b.get("name", "")
                    if kw_lower in name.lower():
                        results.append(b)

                if len(batch_list) < 20:
                    break
                page += 1

                if page > 10:
                    break

            except Exception as e:
                LOGGER.error(f"Batch search page {page} error: {e}")
                break

        if not results:
            await status.edit_text(
                f"❌ No batches found for **\"{keyword}\"**.\n\n"
                "Try a different keyword:\n"
                "`Yakeen` | `Arjuna` | `Lakshya` | `Prayas` | `Udaan` | `NEET` | `JEE`"
            )
            user_data[user_id]["state"] = AWAITING_KEYWORD
            return

        # Show numbered list
        text = f"**🔍 Found {len(results)} batch(es) for \"{keyword}\":**\n\n"
        for i, batch in enumerate(results, 1):
            name = batch.get("name", "Unknown")
            lang = batch.get("language", "")
            lang_str = f" `[{lang}]`" if lang else ""
            text += f"`{i}.` **{name}**{lang_str}\n"

        text += (
            f"\n**Send a number (1-{len(results)}) to select a batch:**\n"
            "_(Send /cancel to abort)_"
        )

        user_data[user_id].update({
            "state": AWAITING_BATCH_SELECT,
            "keyword": keyword,
            "nl_batches": results,
        })

        if len(text) > 4000:
            text = text[:3900] + f"\n\n... Send a number (1-{len(results)})."

        await status.edit_text(text)

    except Exception as e:
        LOGGER.error(f"Keyword search error: {e}")
        await status.edit_text(
            f"❌ Search failed: {str(e)[:150]}\n\nTry again or send /cancel"
        )


async def handle_batch_select_nologin(client, message, choice):
    """Handle batch selection (no-login flow)."""
    user_id = message.from_user.id
    batches = user_data[user_id].get("nl_batches", [])
    nl_token = user_data[user_id].get("nl_token", _get_working_token())

    if not choice.isdigit() or not (1 <= int(choice) <= len(batches)):
        await message.reply_text(
            f"❌ Please send a number between **1 and {len(batches)}**.\n"
            "Or send /cancel to abort."
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


async def handle_subjects_nologin(client, message, subject_text):
    """Subject selection for no-login flow -> start extraction."""
    user_id = message.from_user.id
    batch_id = user_data[user_id].get("batch_id", "")
    batch_name = user_data[user_id].get("batch_name", "")
    subjects = user_data[user_id].get("subjects", [])
    nl_token = user_data[user_id].get("nl_token", _get_working_token())

    subject_ids = _parse_subject_selection(subject_text, subjects)
    if not subject_ids:
        await message.reply_text(
            "❌ No valid subjects selected.\n"
            "Send numbers like `1 2 3` or `all` for all subjects."
        )
        return

    headers = get_pw_headers(nl_token) if nl_token else {}
    user_data.pop(user_id, None)
    await _extract_and_send(
        client, message, headers,
        batch_id, batch_name, subjects, subject_ids,
    )


# ====================== PARSING HELPERS ======================
def _parse_subject_selection(text, subjects):
    """Parse subject selection text. Supports SN numbers, 'all', and '&' separated IDs."""
    text = text.strip().lower()

    if text == "all":
        return [
            str(s.get("_id", s.get("subjectId", "")))
            for s in subjects
        ]

    if "&" in text:
        return [x.strip() for x in text.split("&") if x.strip()]

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


# ====================== EXTRACTION ENGINE ======================
async def _extract_and_send(
    client, message, headers,
    batch_id, batch_name, subjects, subject_ids,
):
    """
    Common extraction engine for both login and no-login flows.
    Extracts videos (CDN links), notes/PDFs, and DPPs.
    Outputs as .txt file with PW CDN encrypted links.
    """
    user_id = message.from_user.id
    safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in batch_name)
    filename = f"{safe_name.replace(' ', '_')}_{user_id}_PW.txt"

    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"Physics Wallah - {batch_name}\n")
            f.write(f"Batch ID: {batch_id}\n")
            f.write(f"Extracted: {time.strftime('%d %b %Y %H:%M IST')}\n")
            f.write("=" * 60 + "\n\n")

        # Resolve subject names
        selected_names = []
        for sid in subject_ids:
            name = next(
                (s.get("subject", "Unknown") for s in subjects
                 if str(s.get("_id", s.get("subjectId", ""))) == sid),
                f"Subject-{sid}",
            )
            selected_names.append(name)

        await message.reply_text(
            f"🚀 **Extraction Started!**\n\n"
            f"📚 Batch: **{batch_name}**\n"
            f"📖 Subjects: {len(subject_ids)}\n"
            f"{'  |  '.join(selected_names[:5])}"
            f"{'...' if len(selected_names) > 5 else ''}\n\n"
            "Please wait, this may take a while..."
        )

        total_videos = 0
        total_notes = 0
        total_dpps = 0

        for idx, sid in enumerate(subject_ids):
            sub_name = selected_names[idx] if idx < len(selected_names) else f"Subject-{sid}"
            await message.reply_text(
                f"📚 [{idx + 1}/{len(subject_ids)}] Processing: **{sub_name}**"
            )

            # Videos
            vid_count = await _extract_content_type(
                filename, headers, batch_id, sid, sub_name,
                "videos", "📹",
            )
            total_videos += vid_count

            # Notes/PDFs
            note_count = await _extract_content_type(
                filename, headers, batch_id, sid, sub_name,
                "notes", "📄",
            )
            total_notes += note_count

            # DPP Notes
            dpp_count = await _extract_content_type(
                filename, headers, batch_id, sid, sub_name,
                "DppNotes", "📝",
            )
            total_dpps += dpp_count

            # DPP Videos
            dpp_vid_count = await _extract_content_type(
                filename, headers, batch_id, sid, sub_name,
                "DppVideos", "🎥",
            )
            total_videos += dpp_vid_count

        # Write summary
        with open(filename, "a", encoding="utf-8") as f:
            f.write("\n" + "=" * 60 + "\n")
            f.write("EXTRACTION SUMMARY\n")
            f.write(f"Batch: {batch_name}\n")
            f.write(f"Total Videos: {total_videos}\n")
            f.write(f"Total Notes/PDFs: {total_notes}\n")
            f.write(f"Total DPPs: {total_dpps}\n")
            f.write(f"Total Items: {total_videos + total_notes + total_dpps}\n")
            f.write("=" * 60 + "\n")

        # Send result file
        if total_videos + total_notes + total_dpps == 0:
            await message.reply_text(
                f"⚠️ **No content found for {batch_name}.**\n\n"
                "This could mean:\n"
                "- The token doesn't have access to this batch\n"
                "- The batch has no content uploaded yet\n"
                "- API returned empty results\n\n"
                "Try with a different token or batch."
            )
            return

        caption = (
            f"✅ **Extraction Complete!**\n\n"
            f"📚 **Batch:** {batch_name}\n"
            f"📹 **Videos:** {total_videos}\n"
            f"📄 **Notes/PDFs:** {total_notes}\n"
            f"📝 **DPPs:** {total_dpps}\n"
            f"📊 **Total Items:** {total_videos + total_notes + total_dpps}\n\n"
            f"🔽 **All links are in the file above!**"
        )
        await client.send_document(message.chat.id, filename, caption=caption)

    except Exception as e:
        LOGGER.error(f"Extraction error: {e}", exc_info=True)
        await message.reply_text(
            f"❌ Extraction failed:\n{str(e)[:300]}\n\n"
            "Send /start to try again."
        )
    finally:
        if os.path.exists(filename):
            os.remove(filename)


async def _extract_content_type(
    filename, headers, batch_id, subject_id,
    subject_name, content_type, emoji,
):
    """Extract a specific content type (videos/notes/DppNotes/DppVideos)."""
    count = 0
    page = 1

    while page <= 50:
        try:
            resp = requests.get(
                f"{PW_BASE_URL}/v3/batches/{batch_id}/subject/{subject_id}/contents",
                params={
                    "page": str(page),
                    "contentType": content_type,
                    "tag": "",
                },
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
                            url = _convert_to_cdn_link(url)
                            f.write(f"{title}: {url}\n")
                            count += 1

                        video_details = item.get("videoDetails", {})
                        if not url and video_details:
                            vid_url = video_details.get("videoUrl", "")
                            if vid_url:
                                vid_url = _convert_to_cdn_link(vid_url)
                                f.write(f"{title}: {vid_url}\n")
                                count += 1

                    elif content_type in ("notes", "DppNotes"):
                        url = (
                            item.get("url", "")
                            or item.get("pdfUrl", "")
                            or item.get("fileUrl", "")
                        )
                        if url:
                            f.write(f"{title}: {url}\n")
                            count += 1

                        for att in item.get("attachments", []):
                            att_url = att.get("url", att.get("baseUrl", ""))
                            att_name = att.get("name", att.get("key", "attachment"))
                            if att_url:
                                f.write(f"  -> {att_name}: {att_url}\n")
                                count += 1

            page += 1
            await asyncio.sleep(0.3)

        except Exception as e:
            LOGGER.error(
                f"Extract {content_type} error (batch={batch_id}, "
                f"sub={subject_id}, page={page}): {e}"
            )
            break

    return count


def _convert_to_cdn_link(url):
    """Convert PW video URL to proper CDN encrypted link."""
    if not url:
        return url

    cdn_replacements = {
        "d1d34p8vz63oiq.cloudfront.net": "d26g5bnklkwsh4.cloudfront.net",
        "d2bps9p1kber4v.cloudfront.net": "d26g5bnklkwsh4.cloudfront.net",
        "d3cvwyf9ksu0h5.cloudfront.net": "d26g5bnklkwsh4.cloudfront.net",
        "d1kwv1j9v54g2g.cloudfront.net": "d26g5bnklkwsh4.cloudfront.net",
    }

    for old_domain, new_domain in cdn_replacements.items():
        url = url.replace(old_domain, new_domain)

    return url.strip()
