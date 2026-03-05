"""
PW Extraction Module — Complete Robust Version
Fixed:
  - OTP body: username + organizationId (real PW web API format)
  - Token: client_id="system-admin", resp["data"]["access_token"]
  - Notes extraction added (was missing before)
  - Without Login: 4-layer fallback — NEVER shows "not found" without giving options
"""
import requests
import asyncio
import os
import re
import json
import uuid
import logging
from Extractor import app

LOGGER = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────
ORG_ID        = "5eb393ee95fab7468a79d189"
CLIENT_SECRET = "KjPXuAVfC5xbmgreETNMaL7z"
OTP_URL       = "https://api.penpencil.co/v1/users/get-otp"
TOKEN_URL     = "https://api.penpencil.co/v3/oauth/token"

# ─────────────────────────────────────────────────────────────
# HEADERS
# ─────────────────────────────────────────────────────────────
def _web_h() -> dict:
    return {
        "Content-Type":     "application/json",
        "Client-Id":        ORG_ID,
        "Client-Type":      "WEB",
        "Client-Version":   "2.6.12",
        "Integration-With": "Origin",
        "Randomid":         uuid.uuid4().hex,
        "Referer":          "https://www.pw.live/",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }

def _mob_h(token: str = "") -> dict:
    h = {
        "client-id":      ORG_ID,
        "client-version": "12.84",
        "user-agent":     "Android",
        "randomid":       uuid.uuid4().hex,
        "client-type":    "MOBILE",
        "content-type":   "application/json",
    }
    if token:
        h["authorization"] = f"Bearer {token}"
    return h

def _all_h(token: str = "") -> list:
    """Multiple header combos tried in order."""
    combos = [_web_h(), _mob_h(token)]
    if token:
        wh = _web_h()
        wh["authorization"] = f"Bearer {token}"
        combos.insert(0, wh)
    return combos

# ─────────────────────────────────────────────────────────────
# API HELPERS
# ─────────────────────────────────────────────────────────────
def _post(url: str, body: dict, timeout: int = 15) -> dict:
    try:
        return requests.post(url, json=body, headers=_web_h(), timeout=timeout).json()
    except Exception as e:
        LOGGER.error(f"POST {url}: {e}")
        return {}

def _get_robust(url: str, params: dict = None, token: str = "", timeout: int = 20) -> dict:
    """GET with multiple header combos, returns first non-empty response."""
    for h in _all_h(token):
        try:
            r = requests.get(url, params=params, headers=h, timeout=timeout)
            if r.status_code == 200:
                d = r.json()
                if d.get("data"):
                    return d
        except Exception as e:
            LOGGER.warning(f"GET attempt failed {url}: {e}")
    return {}

# ─────────────────────────────────────────────────────────────
# ENTRY POINTS (called by start.py)
# ─────────────────────────────────────────────────────────────
async def pw_mobile(client, message):
    cid = message.chat.id

    phone_msg = await app.ask(
        cid,
        "**📱 Send your mobile number (without +91)**\n"
        "Example: `9876543210`\n\n"
        "_Send /cancel to abort._",
        filters=None,
    )
    if phone_msg.text.strip() == "/cancel":
        await message.reply_text("❌ Cancelled.")
        return

    phone = phone_msg.text.strip()
    if not phone.isdigit() or len(phone) != 10:
        await message.reply_text("❌ Invalid number. Use /start to retry.")
        return

    # Send OTP — fixed body format
    s = await message.reply_text("⏳ Sending OTP…")
    _post(f"{OTP_URL}?smsType=0", {
        "username":       phone,
        "countryCode":    "+91",
        "organizationId": ORG_ID,
    })
    await s.edit_text(
        "✅ **OTP sent!**\n"
        "🔢 Now send the OTP you received.\n\n"
        "_Send /cancel to abort._"
    )

    otp_msg = await app.ask(cid, "🔐 OTP:", filters=None)
    if otp_msg.text.strip() == "/cancel":
        await message.reply_text("❌ Cancelled.")
        return

    otp = otp_msg.text.strip()
    s2  = await message.reply_text("⏳ Verifying…")

    # Get token — FIXED: client_id="system-admin", correct response path
    resp  = _post(TOKEN_URL, {
        "username":       phone,
        "otp":            otp,
        "client_id":      "system-admin",
        "client_secret":  CLIENT_SECRET,
        "grant_type":     "password",
        "organizationId": ORG_ID,
        "latitude":       0,
        "longitude":      0,
    })
    token = (resp.get("data") or {}).get("access_token")
    if not token:
        err = resp.get("message", str(resp)[:100])
        await s2.edit_text(f"❌ **Login failed:** {err}\n\nUse /start to retry.")
        return

    await s2.edit_text("✅ **Logged in!** Fetching batches…")
    await _login_flow(client, message, token)


async def pw_token(client, message):
    cid = message.chat.id
    tok_msg = await app.ask(
        cid,
        "**🔑 Paste your PW Bearer Token**\n\n"
        "Get it from:\n"
        "• Browser DevTools → Network tab\n"
        "• PW Token Generator\n\n"
        "_Send /cancel to abort._",
        filters=None,
    )
    if tok_msg.text.strip() == "/cancel":
        await message.reply_text("❌ Cancelled.")
        return
    token = tok_msg.text.strip()
    await message.reply_text("✅ Token received! Fetching batches…")
    await _login_flow(client, message, token)


async def pw_nologin(client, message):
    cid = message.chat.id
    kw_msg = await app.ask(
        cid,
        "**🔓 Without Login — PW Batch Search**\n\n"
        "Type a **batch keyword**:\n"
        "`Yakeen` · `Arjuna` · `Lakshya` · `Prayas` · `JEE` · `NEET`\n\n"
        "💡 Or paste a **direct Batch ID** (24-char)\n"
        "   _(get from pw.live URL or a friend)_\n\n"
        "_Send /cancel to abort._",
        filters=None,
    )
    if kw_msg.text.strip() == "/cancel":
        await message.reply_text("❌ Cancelled.")
        return

    inp = kw_msg.text.strip()

    # Direct batch ID shortcut
    if len(inp) == 24 and all(c in "0123456789abcdefABCDEF" for c in inp):
        await _nologin_batch(client, message, inp, inp)
        return

    await _nologin_search(client, message, inp)

# ─────────────────────────────────────────────────────────────
# LOGIN FLOW
# ─────────────────────────────────────────────────────────────
async def _login_flow(client, message, token: str):
    cid = message.chat.id

    resp    = _get_robust("https://api.penpencil.co/v3/batches/my-batches", token=token)
    batches = resp.get("data", [])
    if not batches:
        await message.reply_text("❌ No batches found. Token may be invalid or expired.")
        return

    txt = "**📚 Your Enrolled Batches:**\n\n"
    for d in batches:
        txt += f"**{d['name']}** : `{d['_id']}`\n"
    txt += "\n**Send the Batch ID to extract:**"
    await message.reply_text(txt)

    bid_msg = await app.ask(cid, "📌 Batch ID:", filters=None)
    if bid_msg.text.strip() == "/cancel":
        await message.reply_text("❌ Cancelled.")
        return

    batch_id   = bid_msg.text.strip()
    batch_name = next((d["name"] for d in batches if d["_id"] == batch_id), batch_id)

    result = await _fetch_subjects(message, batch_id, token=token)
    if result is None:
        return
    subjects, all_ids_str = result

    sub_txt  = "**📖 Subjects:**\n\n"
    sub_txt += "\n".join(
        f"**{s.get('subject', s.get('name', '?'))}** : `{s.get('_id', s.get('subjectId', ''))}`"
        for s in subjects
    )
    sub_txt += f"\n\n**Send IDs with `&`**\nAll: `{all_ids_str}`"
    await message.reply_text(sub_txt)

    sub_msg = await app.ask(cid, "📌 Subject IDs:", filters=None)
    if sub_msg.text.strip() == "/cancel":
        await message.reply_text("❌ Cancelled.")
        return

    sids = [x.strip() for x in sub_msg.text.split("&") if x.strip()]
    await _extract_and_send(client, message, batch_id, batch_name, subjects, sids, token=token)

# ─────────────────────────────────────────────────────────────
# WITHOUT LOGIN: 4-LAYER SEARCH
# ─────────────────────────────────────────────────────────────
async def _nologin_search(client, message, keyword: str):
    cid = message.chat.id
    s   = await message.reply_text(
        f"🔍 Searching **\"{keyword}\"**…\n_Trying multiple methods_"
    )

    batches = []

    # ── Layer 1: PW API v3 ──────────────────────────────────
    if not batches:
        for h in _all_h():
            try:
                for pg in range(1, 5):
                    r = requests.get(
                        "https://api.penpencil.co/v3/batches",
                        params={
                            "organizationId": ORG_ID,
                            "search":         keyword,
                            "page":           str(pg),
                            "limit":          "10",
                            "tag":            "",
                        },
                        headers=h, timeout=15,
                    ).json()
                    data = r.get("data", [])
                    if not data:
                        break
                    batches.extend(data)
                    if len(data) < 10:
                        break
                if batches:
                    break
            except Exception as e:
                LOGGER.warning(f"L1: {e}")

    # ── Layer 2: PW API v2 ──────────────────────────────────
    if not batches:
        try:
            r = requests.get(
                "https://api.penpencil.co/v2/batches",
                params={"organizationId": ORG_ID, "search": keyword, "page": "1"},
                headers=_web_h(), timeout=15,
            ).json()
            batches = r.get("data", [])
        except Exception as e:
            LOGGER.warning(f"L2: {e}")

    # ── Layer 3: Scrape pw.live (__NEXT_DATA__) ─────────────
    if not batches:
        try:
            site_r = requests.get(
                "https://www.pw.live/study/batches",
                params={"search": keyword},
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept":     "text/html,application/xhtml+xml,*/*;q=0.8",
                    "Referer":    "https://www.pw.live/",
                },
                timeout=20,
            )
            m = re.search(
                r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
                site_r.text, re.DOTALL,
            )
            if m:
                nd    = json.loads(m.group(1))
                props = nd.get("props", {}).get("pageProps", {})
                for key in ("batches", "data", "items", "batchList", "results", "batchData"):
                    val = props.get(key, [])
                    if isinstance(val, list) and val:
                        batches = val
                        LOGGER.info(f"L3 scrape got {len(batches)} from key '{key}'")
                        break
        except Exception as e:
            LOGGER.warning(f"L3: {e}")

    # ── Layer 4: All failed — guide user ────────────────────
    if not batches:
        await s.edit_text(
            f"⚠️ **Search failed for \"{keyword}\"**\n\n"
            "**What you can do:**\n\n"
            "1️⃣ **Enter Batch ID directly** _(always works)_\n"
            "   → Open pw.live in browser\n"
            "   → Find your batch → look at URL\n"
            "   → Copy the 24-char ID\n\n"
            "2️⃣ **Try a different keyword**\n"
            "   e.g. `Yakeen` · `Arjuna` · `Lakshya` · `NEET` · `JEE`\n\n"
            "3️⃣ **Use Login method** (100% guaranteed)\n"
            "   → /start → Physics Wallah → Mobile OTP\n\n"
            "📌 **Reply with Batch ID or new keyword:**"
        )
        retry = await app.ask(cid, "📌 Enter Batch ID or new keyword:", filters=None)
        if retry.text.strip() == "/cancel":
            await message.reply_text("❌ Cancelled. Use /start to restart.")
            return

        val = retry.text.strip()
        if len(val) == 24 and all(c in "0123456789abcdefABCDEF" for c in val):
            await _nologin_batch(client, message, val, val)
        else:
            await _nologin_search(client, message, val)
        return

    # ── Show search results ──────────────────────────────────
    txt = f"**🔍 {len(batches)} batch(es) found for \"{keyword}\":**\n\n"
    for i, b in enumerate(batches, 1):
        name = b.get("name", "Unknown")
        lang = b.get("language", "")
        txt += f"`{i}.` **{name}**" + (f"  `[{lang}]`" if lang else "") + "\n"
    txt += f"\n**Send number (1–{len(batches)}) to select:**\n_(/cancel to abort)_"
    await s.edit_text(txt)

    sel_msg = await app.ask(cid, "📌 Select:", filters=None)
    if sel_msg.text.strip() == "/cancel":
        await message.reply_text("❌ Cancelled.")
        return

    sel = sel_msg.text.strip()
    if not sel.isdigit() or not (1 <= int(sel) <= len(batches)):
        await message.reply_text(f"❌ Invalid. Send 1–{len(batches)}. Use /start to retry.")
        return

    chosen     = batches[int(sel) - 1]
    batch_id   = chosen.get("_id", "")
    batch_name = chosen.get("name", batch_id)
    await _nologin_batch(client, message, batch_id, batch_name)


async def _nologin_batch(client, message, batch_id: str, batch_name: str):
    cid    = message.chat.id
    result = await _fetch_subjects(message, batch_id)
    if result is None:
        return
    subjects, all_ids_str = result

    sub_msg = await app.ask(
        cid,
        f"**📖 Subjects in {batch_name}:**\n\n"
        + "\n".join(
            f"**{s.get('subject', s.get('name', '?'))}** : "
            f"`{s.get('_id', s.get('subjectId', ''))}`"
            for s in subjects
        )
        + f"\n\n**Send IDs with `&`**\nAll: `{all_ids_str}`\n\n_(/cancel to abort)_",
        filters=None,
    )
    if sub_msg.text.strip() == "/cancel":
        await message.reply_text("❌ Cancelled.")
        return

    sids = [x.strip() for x in sub_msg.text.split("&") if x.strip()]
    await _extract_and_send(client, message, batch_id, batch_name, subjects, sids)

# ─────────────────────────────────────────────────────────────
# SHARED: FETCH SUBJECTS
# ─────────────────────────────────────────────────────────────
async def _fetch_subjects(message, batch_id: str, token: str = ""):
    """Returns (subjects_list, all_ids_str) or None on failure."""
    s        = await message.reply_text("⏳ Fetching subjects…")
    subjects = []

    for h in _all_h(token):
        try:
            r = requests.get(
                f"https://api.penpencil.co/v3/batches/{batch_id}/details",
                headers=h, timeout=20,
            ).json()
            subs = r.get("data", {}).get("subjects", [])
            if subs:
                subjects = subs
                break
        except Exception as e:
            LOGGER.warning(f"Subjects /details: {e}")

    if not subjects:
        for h in _all_h(token):
            try:
                r = requests.get(
                    f"https://api.penpencil.co/v3/batches/{batch_id}/subjects",
                    headers=h, timeout=20,
                ).json()
                subs = r.get("data", [])
                if subs:
                    subjects = subs
                    break
            except Exception as e:
                LOGGER.warning(f"Subjects /subjects: {e}")

    await s.delete()

    if not subjects:
        await message.reply_text(
            "❌ **Could not fetch subjects.**\n\n"
            "Possible reasons:\n"
            "• Batch ID is wrong or private\n"
            "• Batch requires subscription\n\n"
            "👉 Try Login method: /start → Mobile OTP"
        )
        return None

    all_ids = [str(s.get("_id", s.get("subjectId", ""))) for s in subjects]
    return subjects, "&".join(filter(None, all_ids))

# ─────────────────────────────────────────────────────────────
# EXTRACTION ENGINE
# ─────────────────────────────────────────────────────────────
async def _extract_and_send(client, message, batch_id, batch_name, subjects, sids, token=""):
    uid    = getattr(message.from_user, "id", message.chat.id)
    fname  = f"{batch_name.replace(' ', '_')[:40]}_{uid}_PW.txt"
    status = await message.reply_text(
        f"🚀 **Extracting {len(sids)} subject(s)…**\n_This may take a few minutes._"
    )
    total_v = total_n = 0

    try:
        with open(fname, "w", encoding="utf-8") as f:
            f.write(f"Physics Wallah — {batch_name}\n{'='*50}\n\n")

        for sid in sids:
            sub_name = next(
                (s.get("subject", s.get("name", sid))
                 for s in subjects
                 if str(s.get("_id", s.get("subjectId", ""))) == sid),
                sid,
            )
            await status.edit_text(f"📚 **{sub_name}**…")

            for ctype in ("videos", "notes"):
                page = 1
                while True:
                    result = {}
                    for h in _all_h(token):
                        try:
                            r = requests.get(
                                f"https://api.penpencil.co/v3/batches/{batch_id}"
                                f"/subject/{sid}/contents",
                                params={"page": str(page), "contentType": ctype, "tag": ""},
                                headers=h, timeout=20,
                            ).json()
                            if r.get("data"):
                                result = r
                                break
                        except Exception as e:
                            LOGGER.warning(f"{ctype} p{page}: {e}")

                    data = result.get("data", [])
                    if not data:
                        break

                    icon = "📹" if ctype == "videos" else "📄"
                    with open(fname, "a", encoding="utf-8") as f:
                        f.write(f"\n{icon} {sub_name} — {ctype.capitalize()} (Page {page})\n")
                        f.write("-" * 40 + "\n")
                        for item in data:
                            raw = item.get("url", "")
                            if not raw:
                                continue
                            title = item.get("topic", item.get("title", "Unknown"))
                            if ctype == "videos":
                                url = (raw
                                       .replace("d1d34p8vz63oiq", "d26g5bnklkwsh4")
                                       .replace(".mpd", ".m3u8").strip())
                                total_v += 1
                            else:
                                url = raw.strip()
                                total_n += 1
                            f.write(f"{title}:{url}\n")

                    page += 1
                    await asyncio.sleep(0.5)

        await status.delete()
        await client.send_document(
            message.chat.id, fname,
            caption=(
                f"✅ **Done!**\n\n"
                f"📚 **{batch_name}**\n"
                f"📹 Videos: `{total_v}`\n"
                f"📄 Notes:  `{total_n}`"
            ),
        )

    except Exception as e:
        LOGGER.error(f"Extraction: {e}", exc_info=True)
        try:
            await status.edit_text(f"❌ Extraction failed:\n`{str(e)[:200]}`")
        except Exception:
            pass
    finally:
        if os.path.exists(fname):
            os.remove(fname)
