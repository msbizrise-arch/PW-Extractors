"""
PW (Physics Wallah) Extraction Module - Advanced Build v2.0
Fixed: OTP sending, Token validation, Batch fetching, Without Login
Features:
  - Login via Mobile OTP (fixed: proper PW API v3 endpoints with correct headers)
  - Login via Direct Token (fixed: validation + duplicate token support)
  - Without Login (keyword-based batch search with universal token)
  - All batch listings with SN numbers (1, 2, 3...)
  - User selects by SN number
  - Full extraction: Videos (CDN links) + PDFs/Notes + DPPs
  - /cancel command support
"""
import requests
import asyncio
import os
import logging
from pyrogram import filters
from Extractor import app
from config import (
    PW_ORG_ID, PW_CLIENT_SECRET, PW_BASE_URL, PW_UNIVERSAL_TOKEN,
    PW_HEADERS_TEMPLATE, PW_WEB_HEADERS
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

# ====================== PW API HEADERS ======================
def get_pw_headers(token: str = None) -> dict:
    """Build PW API headers with given bearer token."""
    headers = PW_HEADERS_TEMPLATE.copy()
    if token:
        headers["authorization"] = f"Bearer {token}"
    return headers


def get_pw_web_headers(token: str = None) -> dict:
    """Build PW Web headers for browser-like requests."""
    headers = PW_WEB_HEADERS.copy()
    if token:
        headers["authorization"] = f"Bearer {token}"
    return headers


def _validate_token(token: str) -> dict:
    """Validate a PW token by calling profile endpoint. Returns user data or error."""
    headers = get_pw_headers(token)
    try:
        resp = requests.get(
            f"{PW_BASE_URL}/v3/users/details",
            headers=headers,
            timeout=15,
        )
        data = resp.json()
        if resp.status_code == 200 and data.get("success"):
            return {"valid": True, "data": data.get("data", {})}
        return {"valid": False, "error": data.get("message", "Invalid token")}
    except Exception as e:
        return {"valid": False, "error": str(e)}


def _get_working_token() -> str:
    """Return the universal token from env if set, else empty string."""
    return PW_UNIVERSAL_TOKEN.strip() if PW_UNIVERSAL_TOKEN else ""


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
        await message.reply_text("No active operation to cancel.\nSend /start to begin.")


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
        "- Browser DevTools → Network tab → Authorization header\n"
        "- PW App (intercept traffic)\n\n"
        "Even expired tokens may work for some batches.\n"
        "Send /cancel to abort."
    )


async def pw_nologin(client, message):
    """Start Without Login flow — keyword-based batch search."""
    user_id = message.chat.id
    token = _get_working_token()

    if not token:
        # No universal token configured — ask user for one
        user_data[user_id] = {"state": AWAITING_NL_TOKEN}
        await client.send_message(
            user_id,
            "**🔓 Without Login — PW Batch Access**\n\n"
            "No universal token is configured.\n"
            "Please send a **working PW Bearer Token** to access batches.\n\n"
            "This token will be used to search and extract all PW batches.\n"
            "A universal token gives access to all batches.\n\n"
            "Send /cancel to abort."
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
        "Send /cancel to abort."
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
        return  # No active conversation

    state = user_data[user_id].get("state")

    try:
        # ── Login-based states ──
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

        # ── Without Login states ──
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


# ====================== LOGIN-BASED STATE HANDLERS ======================
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

    try:
        # FIXED: Use proper v3 endpoint with correct headers
        resp = requests.post(
            f"{PW_BASE_URL}/v3/users/get-otp",
            json={
                "username": f"+91{phone}",
                "organizationId": PW_ORG_ID,
                "otpType": "login",
            },
            headers=get_pw_headers(),
            timeout=15,
        )
        data = resp.json()
        LOGGER.info(f"OTP send response: {data}")

        if resp.status_code == 200 and data.get("success", False):
            user_data[user_id]["phone"] = phone
            user_data[user_id]["state"] = AWAITING_OTP
            await status.edit_text(
                "✅ **OTP sent to your number!**\n\n"
                "🔢 **Now send the OTP you received.**\n\n"
                "Send /cancel to abort."
            )
        elif "too many requests" in str(data).lower() or resp.status_code == 429:
            # Rate limit - try alternative endpoint
            await status.edit_text(
                "⚠️ **Rate limit hit. Trying alternative method...**"
            )
            # Try v1 endpoint as fallback
            resp2 = requests.post(
                f"{PW_BASE_URL}/v1/users/get-otp",
                json={
                    "username": f"+91{phone}",
                    "organizationId": PW_ORG_ID,
                },
                headers={
                    "Content-Type": "application/json",
                    "client-id": PW_ORG_ID,
                    "client-type": "MOBILE",
                    "client-version": "12.84",
                },
                timeout=15,
            )
            data2 = resp2.json()
            LOGGER.info(f"OTP fallback response: {data2}")
            
            if resp2.status_code == 200 and data2.get("success", False):
                user_data[user_id]["phone"] = phone
                user_data[user_id]["state"] = AWAITING_OTP
                await status.edit_text(
                    "✅ **OTP sent to your number!**\n\n"
                    "🔢 **Now send the OTP you received.**\n\n"
                    "Send /cancel to abort."
                )
            else:
                err = data2.get("message", data2.get("error", {}).get("message", "Unknown error"))
                await status.edit_text(
                    f"❌ **Failed to send OTP:** {err}\n\n"
                    "Please wait a few minutes and try again.\n"
                    "Try again with /start"
                )
                user_data.pop(user_id, None)
        else:
            err = data.get("message", data.get("error", {}).get("message", "Unknown error"))
            await status.edit_text(
                f"❌ **Failed to send OTP:** {err}\n\n"
                "Make sure you have a PW account with this number.\n"
                "Try again with /start"
            )
            user_data.pop(user_id, None)

    except Exception as e:
        LOGGER.error(f"OTP send error: {e}")
        await status.edit_text(
            "❌ Network error while sending OTP.\n"
            "Please try again with /start"
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

    try:
        # FIXED: Use proper OAuth token endpoint with correct parameters
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
            headers=get_pw_headers(),
            timeout=15,
        )
        data = resp.json()
        LOGGER.info(f"OTP verify response: {data}")

        if "access_token" in data or "token" in data:
            token = data.get("access_token", data.get("token", ""))
            refresh = data.get("refresh_token", "")
            user_data[user_id]["token"] = token
            user_data[user_id]["refresh_token"] = refresh

            token_msg = (
                "✅ **Login Successful!**\n\n"
                f"🔑 **Your Token (save it):**\n"
                f"`{token[:60]}...`\n\n"
                "You can use this token with **Direct Token** login next time.\n"
                "Fetching your batches..."
            )
            await status.edit_text(token_msg)
            await show_batches_login(client, message, token)
        else:
            err = data.get("message", data.get("error", {}).get("message", "Unknown error"))
            await status.edit_text(
                f"❌ **OTP verification failed:** {err}\n\n"
                "Check if the OTP is correct and try again.\n"
                "Send /start to restart."
            )
            user_data.pop(user_id, None)

    except Exception as e:
        LOGGER.error(f"OTP verify error: {e}")
        await status.edit_text(
            "❌ Error verifying OTP. Please try again with /start"
        )
        user_data.pop(user_id, None)


async def handle_token_input(client, message, token):
    """Handle direct token input — validate and fetch batches."""
    user_id = message.from_user.id
    token = token.strip()

    # Remove "Bearer " prefix if user pastes full header
    if token.lower().startswith("bearer "):
        token = token[7:].strip()

    status = await message.reply_text("🔍 Validating token...")

    # Store token and try fetching batches
    user_data[user_id]["token"] = token
    headers = get_pw_headers(token)

    try:
        # FIXED: Try multiple endpoints for batch fetching
        resp = requests.get(
            f"{PW_BASE_URL}/v3/batches/my-batches",
            headers=headers,
            timeout=20,
        )
        data = resp.json()
        batches = data.get("data", [])

        if batches:
            await status.edit_text(
                "✅ **Token accepted!** Fetching batches..."
            )
            await show_batches_login(client, message, token)
        elif resp.status_code == 401:
            # Token might be expired — inform user but still try
            await status.edit_text(
                "⚠️ **Token may be expired or invalid.**\n\n"
                "But trying to fetch batches anyway...\n"
                "If no batches found, please get a fresh token.\n\n"
                "You can get a new token via **📱 Mobile OTP** login."
            )
            await show_batches_login(client, message, token)
        else:
            await status.edit_text(
                "✅ **Token received!** Fetching batches..."
            )
            await show_batches_login(client, message, token)

    except Exception as e:
        LOGGER.error(f"Token validation error: {e}")
        await status.edit_text(
            "❌ Error validating token. Trying to fetch batches anyway..."
        )
        await show_batches_login(client, message, token)


async def show_batches_login(client, message, token):
    """Fetch and display user's batches (login flow) with SN numbers."""
    user_id = message.chat.id
    headers = get_pw_headers(token)

    try:
        # FIXED: Try multiple endpoints for fetching batches
        batches = []
        
        # Try my-batches endpoint first
        resp = requests.get(
            f"{PW_BASE_URL}/v3/batches/my-batches",
            headers=headers,
            timeout=20,
        )
        data = resp.json()
        batches = data.get("data", [])
        
        # If no batches, try alternative endpoint
        if not batches:
            resp2 = requests.get(
                f"{PW_BASE_URL}/v3/batches?organizationId={PW_ORG_ID}&page=1&limit=100",
                headers=headers,
                timeout=20,
            )
            data2 = resp2.json()
            if data2.get("data"):
                batches = data2.get("data", [])

        if not batches:
            err_msg = data.get("message", "")
            await message.reply_text(
                f"❌ **No batches found for this account.**\n"
                f"{'Error: ' + err_msg if err_msg else ''}\n\n"
                "Token may be invalid/expired.\n"
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

        user_data[user_id]["batches"] = batches
        user_data[user_id]["state"] = AWAITING_BATCH
        await message.reply_text(text)

    except Exception as e:
        LOGGER.error(f"Batch fetch error: {e}")
        await message.reply_text(
            f"❌ Failed to fetch batches.\n"
            f"Error: {str(e)[:150]}\n\n"
            "Token may be invalid. Send /start to try again."
        )
        user_data.pop(user_id, None)


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
    headers = get_pw_headers(token)

    status = await message.reply_text(
        f"⏳ Fetching subjects for **{batch_name}**..."
    )

    try:
        resp = requests.get(
            f"{PW_BASE_URL}/v3/batches/{batch_id}/details",
            headers=headers,
            timeout=20,
        )
        details = resp.json()
        subjects = details.get("data", {}).get("subjects", [])

        if not subjects:
            await status.edit_text(
                f"❌ No subjects found for **{batch_name}**.\n"
                "This batch may not have any content yet."
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
            "batch_id": batch_id,
            "batch_name": batch_name,
            "subjects": subjects,
            "state": AWAITING_SUBJECTS,
        })
        await status.edit_text(text)

    except Exception as e:
        LOGGER.error(f"Subject fetch error: {e}")
        await status.edit_text(
            f"❌ Failed to fetch subjects.\nError: {str(e)[:150]}"
        )
        user_data.pop(user_id, None)


async def handle_subjects(client, message, subject_text):
    """Handle subject selection by SN numbers (login flow)."""
    user_id = message.from_user.id
    token = user_data[user_id].get("token", "")
    batch_id = user_data[user_id].get("batch_id", "")
    batch_name = user_data[user_id].get("batch_name", "")
    subjects = user_data[user_id].get("subjects", [])
    headers = get_pw_headers(token)

    # Parse subject selection
    subject_ids = _parse_subject_selection(subject_text, subjects)
    if not subject_ids:
        await message.reply_text(
            "❌ No valid subjects selected.\n"
            "Send numbers like `1 2 3` or `all` for all subjects."
        )
        return

    user_data.pop(user_id, None)
    await _extract_and_send(
        client, message, headers,
        batch_id, batch_name, subjects, subject_ids
    )


# ====================== WITHOUT LOGIN STATE HANDLERS ======================
async def handle_nl_token(client, message, token):
    """Handle token input for without-login flow."""
    user_id = message.from_user.id
    token = token.strip()

    if token.lower().startswith("bearer "):
        token = token[7:].strip()

    status = await message.reply_text("🔍 Validating token...")

    # Test if token works for batch search
    headers = get_pw_headers(token)
    try:
        resp = requests.get(
            f"{PW_BASE_URL}/v3/batches?organizationId={PW_ORG_ID}&page=1&limit=1",
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
            await status.edit_text(
                "⚠️ **Token may not work for batch search.**\n"
                "But I'll try with it anyway.\n\n"
                "Type a **batch keyword** to search:\n"
                "Send /cancel to abort."
            )
            user_data[user_id] = {
                "state": AWAITING_KEYWORD,
                "nl_token": token,
            }

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
    headers = get_pw_headers(nl_token) if nl_token else {}

    status = await message.reply_text(
        f"🔍 Searching batches for **\"{keyword}\"**..."
    )

    try:
        results = []
        page = 1

        while len(results) < 50:
            try:
                # FIXED: Use proper PW batch search endpoint
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
                LOGGER.info(f"Batch search page {page}: {len(data.get('data', []))} results")

                batch_list = data.get("data", [])
                if not batch_list:
                    break

                # Filter by keyword (case-insensitive)
                kw_lower = keyword.lower()
                for b in batch_list:
                    name = b.get("name", "")
                    if kw_lower in name.lower():
                        results.append(b)

                if len(batch_list) < 20:
                    break
                page += 1

                # Safety: don't fetch too many pages
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
            # Don't pop - let user try again
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

        # Handle long messages
        if len(text) > 4000:
            text = text[:3900] + f"\n\n... and more. Send a number (1-{len(results)})."

        await status.edit_text(text)

    except Exception as e:
        LOGGER.error(f"Keyword search error: {e}")
        await status.edit_text(
            f"❌ Search failed: {str(e)[:150]}\n\nTry again or send /cancel"
        )


async def handle_batch_select_nologin(client, message, choice):
    """Handle numbered batch selection from search results (no-login flow)."""
    user_id = message.from_user.id
    batches = user_data[user_id].get("nl_batches", [])
    nl_token = user_data[user_id].get("nl_token", _get_working_token())
    headers = get_pw_headers(nl_token) if nl_token else {}

    if not choice.isdigit() or not (1 <= int(choice) <= len(batches)):
        await message.reply_text(
            f"❌ Please send a number between **1 and {len(batches)}**.\n"
            "Or send /cancel to abort."
        )
        return

    selected = batches[int(choice) - 1]
    batch_id = selected.get("_id", "")
    batch_name = selected.get("name", batch_id)

    status = await message.reply_text(
        f"⏳ Fetching subjects for **{batch_name}**..."
    )

    try:
        resp = requests.get(
            f"{PW_BASE_URL}/v3/batches/{batch_id}/details",
            headers=headers,
            timeout=20,
        )
        details = resp.json()
        subjects = details.get("data", {}).get("subjects", [])

        if not subjects:
            await status.edit_text(
                f"❌ No subjects found for **{batch_name}**.\n\n"
                "This batch may require a valid token.\n"
                "Try **📱 Mobile OTP** or **🔑 Token** method from /start."
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
            "state": AWAITING_SUBJECTS_NL,
            "batch_id": batch_id,
            "batch_name": batch_name,
            "subjects": subjects,
        })
        await status.edit_text(text)

    except Exception as e:
        LOGGER.error(f"Subject fetch (no-login) error: {e}")
        await status.edit_text(
            f"❌ Failed to fetch subjects.\nError: {str(e)[:150]}"
        )
        user_data.pop(user_id, None)


async def handle_subjects_nologin(client, message, subject_text):
    """Subject selection for no-login flow -> start extraction."""
    user_id = message.from_user.id
    batch_id = user_data[user_id].get("batch_id", "")
    batch_name = user_data[user_id].get("batch_name", "")
    subjects = user_data[user_id].get("subjects", [])
    nl_token = user_data[user_id].get("nl_token", _get_working_token())
    headers = get_pw_headers(nl_token) if nl_token else {}

    # Parse subject selection
    subject_ids = _parse_subject_selection(subject_text, subjects)
    if not subject_ids:
        await message.reply_text(
            "❌ No valid subjects selected.\n"
            "Send numbers like `1 2 3` or `all` for all subjects."
        )
        return

    user_data.pop(user_id, None)
    await _extract_and_send(
        client, message, headers,
        batch_id, batch_name, subjects, subject_ids
    )


# ====================== HELPER FUNCTIONS ======================
def _parse_subject_selection(text, subjects):
    """Parse subject selection text. Supports SN numbers, 'all', and & separated IDs."""
    text = text.strip().lower()

    if text == "all":
        return [
            str(s.get("_id", s.get("subjectId", "")))
            for s in subjects
        ]

    # Check if input contains & (old-style subject ID input)
    if "&" in text:
        return [x.strip() for x in text.split("&") if x.strip()]

    # Parse space-separated or comma-separated SN numbers
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


# ====================== SHARED EXTRACTION ENGINE ======================
async def _extract_and_send(
    client, message, headers,
    batch_id, batch_name, subjects, subject_ids,
):
    """
    Common extraction engine for both login and no-login flows.
    Extracts videos (CDN links), notes/PDFs, and DPPs.
    """
    user_id = message.from_user.id
    safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in batch_name)
    filename = f"{safe_name.replace(' ', '_')}_{user_id}_PW.txt"

    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"Physics Wallah - {batch_name}\n")
            f.write(f"Batch ID: {batch_id}\n")
            f.write("=" * 60 + "\n\n")

        # Resolve subject names
        selected_names = []
        for sid in subject_ids:
            name = next(
                (s.get("subject", "Unknown") for s in subjects
                 if str(s.get("_id", s.get("subjectId", ""))) == sid),
                f"Subject-{sid}"
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
                f"📚 [{idx+1}/{len(subject_ids)}] Processing: **{sub_name}**"
            )

            # ── Videos ──
            vid_count = await _extract_content_type(
                filename, headers, batch_id, sid, sub_name,
                "videos", "📹"
            )
            total_videos += vid_count

            # ── Notes/PDFs ──
            note_count = await _extract_content_type(
                filename, headers, batch_id, sid, sub_name,
                "notes", "📄"
            )
            total_notes += note_count

            # ── DPPs ──
            dpp_count = await _extract_content_type(
                filename, headers, batch_id, sid, sub_name,
                "DppNotes", "📝"
            )
            total_dpps += dpp_count

            # Also try "DppVideos"
            dpp_vid_count = await _extract_content_type(
                filename, headers, batch_id, sid, sub_name,
                "DppVideos", "🎥"
            )
            total_videos += dpp_vid_count

        # ── Write summary at end ──
        with open(filename, "a", encoding="utf-8") as f:
            f.write("\n" + "=" * 60 + "\n")
            f.write(f"EXTRACTION SUMMARY\n")
            f.write(f"Batch: {batch_name}\n")
            f.write(f"Total Videos: {total_videos}\n")
            f.write(f"Total Notes/PDFs: {total_notes}\n")
            f.write(f"Total DPPs: {total_dpps}\n")
            f.write("=" * 60 + "\n")

        # ── Send result file ──
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

    while True:
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

                    # Handle video URLs — convert to PW CDN links
                    if content_type in ("videos", "DppVideos"):
                        url = item.get("url", "")
                        if url:
                            # Convert to PW CDN encrypted link format
                            url = _convert_to_cdn_link(url)
                            f.write(f"{title}: {url}\n")
                            count += 1
                        # Also check for videoDetails
                        video_details = item.get("videoDetails", {})
                        if not url and video_details:
                            vid_url = video_details.get("videoUrl", "")
                            if vid_url:
                                vid_url = _convert_to_cdn_link(vid_url)
                                f.write(f"{title}: {vid_url}\n")
                                count += 1

                    # Handle notes/PDFs
                    elif content_type in ("notes", "DppNotes"):
                        # Check multiple URL fields
                        url = (
                            item.get("url", "")
                            or item.get("pdfUrl", "")
                            or item.get("fileUrl", "")
                        )
                        if url:
                            f.write(f"{title}: {url}\n")
                            count += 1

                        # Check attachments array
                        attachments = item.get("attachments", [])
                        for att in attachments:
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

    # PW CDN domain replacements for encrypted links
    cdn_replacements = {
        "d1d34p8vz63oiq.cloudfront.net": "d26g5bnklkwsh4.cloudfront.net",
        "d2bps9p1kber4v.cloudfront.net": "d26g5bnklkwsh4.cloudfront.net",
        "d3cvwyf9ksu0h5.cloudfront.net": "d26g5bnklkwsh4.cloudfront.net",
        "d1kwv1j9v54g2g.cloudfront.net": "d26g5bnklkwsh4.cloudfront.net",
    }

    for old_domain, new_domain in cdn_replacements.items():
        url = url.replace(old_domain, new_domain)

    # Keep original format — PW uses encrypted CDN links
    # Don't convert to m3u8 or mp4 — keep as-is (encrypted CDN)
    return url.strip()
