import requests
import asyncio
import os
from Extractor import app
from pyrogram import filters
from config import PW_ORG_ID, PW_CLIENT_SECRET, PW_BASE_URL

# ====================== OTP + TOKEN FUNCTIONS ======================

async def get_otp(message, phone_no):
    """Send OTP to user's mobile number"""
    url = f"{PW_BASE_URL}/v1/users/get-otp"
    
    headers = {
        "Content-Type": "application/json",
        "Client-Id": PW_ORG_ID,
        "Client-Type": "WEB",
        "Client-Version": "2.6.12",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    data = {
        "username": phone_no,
        "countryCode": "+91",
        "organizationId": PW_ORG_ID
    }
    
    try:
        resp = requests.post(url, json=data, headers=headers, timeout=10)
        if resp.status_code == 200:
            await message.reply_text("✅ **OTP sent successfully!**\n\nCheck your mobile and enter the OTP.")
            return True
        else:
            await message.reply_text(f"❌ **Failed to send OTP**\n\nError: {resp.status_code}")
            return False
    except Exception as e:
        await message.reply_text(f"❌ **Network Error:** `{str(e)}`")
        return False


async def get_token(message, phone_no, otp):
    """Get access token using OTP"""
    url = f"{PW_BASE_URL}/v3/oauth/token"
    
    data = {
        "username": f"+91{phone_no}",
        "otp": otp,
        "client_id": "system-admin",
        "client_secret": PW_CLIENT_SECRET,
        "grant_type": "password",
        "organizationId": PW_ORG_ID,
        "latitude": 0,
        "longitude": 0
    }
    
    headers = {
        "Content-Type": "application/json",
        "Client-Id": PW_ORG_ID,
        "Client-Type": "WEB",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        resp = requests.post(url, json=data, headers=headers, timeout=10)
        result = resp.json()
        
        if "data" in result and "access_token" in result["data"]:
            token = result["data"]["access_token"]
            await message.reply_text("✅ **Login Successful!**")
            return token
        elif "access_token" in result:
            token = result["access_token"]
            await message.reply_text("✅ **Login Successful!**")
            return token
        else:
            await message.reply_text(f"❌ **Invalid OTP!**\n\nPlease try again.")
            return None
    except Exception as e:
        await message.reply_text(f"❌ **Error:** `{str(e)}`")
        return None


# ====================== LOGIN HANDLERS ======================

async def pw_mobile(client, message):
    """Handle mobile + OTP login"""
    try:
        # Ask for mobile number
        phone_msg = await app.ask(
            message.chat.id,
            "**📱 Enter your mobile number**\n\n(Without +91, e.g., 9876543210)\n\n⏱️ Timeout: 60 seconds",
            timeout=60
        )
        phone = phone_msg.text.strip()
        
        # Validate phone number
        if not phone.isdigit() or len(phone) != 10:
            await message.reply_text("❌ **Invalid mobile number!**\n\nPlease send 10 digit number.")
            return
        
        # Send OTP
        if not await get_otp(message, phone):
            return
        
        # Ask for OTP
        otp_msg = await app.ask(
            message.chat.id,
            "**🔢 Enter the OTP**\n\n(6 digit code sent to your mobile)\n\n⏱️ Timeout: 60 seconds",
            timeout=60
        )
        otp = otp_msg.text.strip()
        
        # Get token and proceed
        token = await get_token(message, phone, otp)
        if token:
            await pw_login(message, token)
            
    except asyncio.TimeoutError:
        await message.reply_text("⏱️ **Timeout!**\n\nYou took too long to respond. Please try again.")
    except Exception as e:
        await message.reply_text(f"❌ **Error:** `{str(e)}`")


async def pw_token(client, message):
    """Handle direct token login"""
    try:
        # Ask for token
        token_msg = await app.ask(
            message.chat.id,
            "**🔑 Enter your PW Access Token**\n\n(You can get this from PW app or browser dev tools)\n\n⏱️ Timeout: 60 seconds",
            timeout=60
        )
        token = token_msg.text.strip()
        
        # Proceed with login
        await pw_login(message, token)
        
    except asyncio.TimeoutError:
        await message.reply_text("⏱️ **Timeout!**\n\nYou took too long to respond. Please try again.")
    except Exception as e:
        await message.reply_text(f"❌ **Error:** `{str(e)}`")


# ====================== EXTRACTION FUNCTIONS ======================

async def pw_login(message, token):
    """Main extraction logic"""
    headers = {
        "Host": "api.penpencil.co",
        "authorization": f"Bearer {token}",
        "client-id": PW_ORG_ID,
        "client-version": "12.84",
        "user-agent": "Android",
        "randomid": "e4307177362e86f1",
        "client-type": "MOBILE",
        "content-type": "application/json"
    }
    
    # Step 1: Get Batches
    await message.reply_text("🔄 **Fetching your batches...**")
    
    try:
        resp = requests.get(
            f"{PW_BASE_URL}/v3/batches/my-batches",
            headers=headers,
            timeout=15
        ).json()
        
        batches = resp.get("data", [])
        if not batches:
            await message.reply_text("❌ **No batches found!**\n\nYour token might be expired or you don't have any active batches.")
            return
        
        # Display batches
        batch_text = "**📚 Your Batches:**\n\n"
        for i, batch in enumerate(batches, 1):
            batch_text += f"{i}. **{batch['name']}**\n   ID: `{batch['_id']}`\n\n"
        
        await message.reply_text(batch_text)
        
    except Exception as e:
        await message.reply_text(f"❌ **Error fetching batches:** `{str(e)}`")
        return
    
    # Step 2: Ask for Batch ID
    try:
        batch_msg = await app.ask(
            message.chat.id,
            "**Send the Batch ID**\n\n(Copy and paste the ID from above)\n\n⏱️ Timeout: 60 seconds",
            timeout=60
        )
        batch_id = batch_msg.text.strip()
        
        # Find batch name
        batch_name = next((b['name'] for b in batches if b['_id'] == batch_id), "Unknown Batch")
        
    except asyncio.TimeoutError:
        await message.reply_text("⏱️ **Timeout!** Please try again.")
        return
    
    # Step 3: Get Subjects
    await message.reply_text("🔄 **Fetching subjects...**")
    
    try:
        details = requests.get(
            f"{PW_BASE_URL}/v3/batches/{batch_id}/details",
            headers=headers,
            timeout=15
        ).json()
        
        subjects = details.get("data", {}).get("subjects", [])
        if not subjects:
            await message.reply_text("❌ **No subjects found in this batch!**")
            return
        
        # Display subjects
        sub_text = "**📖 Subjects:**\n\n"
        all_sub_ids = []
        for i, sub in enumerate(subjects, 1):
            sub_text += f"{i}. **{sub['subject']}**\n   ID: `{sub['subjectId']}`\n\n"
            all_sub_ids.append(str(sub['subjectId']))
        
        sub_text += f"\n**All IDs:** `{'&'.join(all_sub_ids)}`"
        await message.reply_text(sub_text)
        
    except Exception as e:
        await message.reply_text(f"❌ **Error fetching subjects:** `{str(e)}`")
        return
    
    # Step 4: Ask for Subject IDs
    try:
        sub_msg = await app.ask(
            message.chat.id,
            f"**Send Subject IDs to extract**\n\nFormat: `1&2&3` (for multiple)\nOr send `all` for all subjects\n\n⏱️ Timeout: 60 seconds",
            timeout=60
        )
        
        if sub_msg.text.strip().lower() == "all":
            subject_ids = all_sub_ids
        else:
            subject_ids = [s.strip() for s in sub_msg.text.split("&") if s.strip()]
        
    except asyncio.TimeoutError:
        await message.reply_text("⏱️ **Timeout!** Please try again.")
        return
    
    # Step 5: Ask for content type
    try:
        type_msg = await app.ask(
            message.chat.id,
            "**Select content type:**\n\n1. **Videos** (M3U8 links)\n2. **Notes** (PDF links)\n3. **Both**\n\nSend: `1`, `2`, or `3`\n\n⏱️ Timeout: 60 seconds",
            timeout=60
        )
        content_type = type_msg.text.strip()
        
    except asyncio.TimeoutError:
        await message.reply_text("⏱️ **Timeout!** Please try again.")
        return
    
    # Step 6: Extract Content
    await message.reply_text("🚀 **Starting extraction...**\n\nThis may take a few minutes depending on the batch size.")
    
    filename = f"{batch_name.replace(' ', '_')}_PW.txt"
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"🎓 Physics Wallah - {batch_name}\n")
        f.write("=" * 50 + "\n\n")
    
    total_videos = 0
    total_notes = 0
    
    for sid in subject_ids:
        subject_name = next((s['subject'] for s in subjects if str(s['subjectId']) == sid), "Unknown")
        await message.reply_text(f"📚 **Processing:** {subject_name}")
        
        # Extract Videos
        if content_type in ["1", "3"]:
            page = 1
            while True:
                try:
                    params = {"page": str(page), "contentType": "videos", "tag": ""}
                    r = requests.get(
                        f"{PW_BASE_URL}/v3/batches/{batch_id}/subject/{sid}/contents",
                        params=params,
                        headers=headers,
                        timeout=15
                    ).json()
                    
                    data = r.get("data", [])
                    if not data:
                        break
                    
                    with open(filename, "a", encoding="utf-8") as f:
                        f.write(f"\n📹 {subject_name} - Videos (Page {page})\n")
                        f.write("-" * 40 + "\n")
                        
                        for item in data:
                            if item.get("url"):
                                title = item.get("topic", item.get("title", "Unknown"))
                                url = item["url"]
                                # Convert to M3U8
                                url = url.replace("d1d34p8vz63oiq", "d26g5bnklkwsh4").replace(".mpd", ".m3u8")
                                f.write(f"{title}:{url}\n")
                                total_videos += 1
                    
                    page += 1
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    print(f"Video extraction error: {e}")
                    break
        
        # Extract Notes
        if content_type in ["2", "3"]:
            page = 1
            while True:
                try:
                    params = {"page": str(page), "contentType": "notes", "tag": ""}
                    r = requests.get(
                        f"{PW_BASE_URL}/v3/batches/{batch_id}/subject/{sid}/contents",
                        params=params,
                        headers=headers,
                        timeout=15
                    ).json()
                    
                    data = r.get("data", [])
                    if not data:
                        break
                    
                    with open(filename, "a", encoding="utf-8") as f:
                        f.write(f"\n📄 {subject_name} - Notes (Page {page})\n")
                        f.write("-" * 40 + "\n")
                        
                        for item in data:
                            if item.get("url"):
                                title = item.get("topic", item.get("title", "Unknown"))
                                url = item["url"]
                                f.write(f"{title}:{url}\n")
                                total_notes += 1
                    
                    page += 1
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    print(f"Notes extraction error: {e}")
                    break
    
    # Send file
    try:
        caption = f"✅ **Extraction Complete!**\n\n"
        caption += f"📚 Batch: {batch_name}\n"
        caption += f"📹 Videos: {total_videos}\n"
        caption += f"📄 Notes: {total_notes}\n\n"
        caption += "🔽 **Download links are ready!**"
        
        await app.send_document(
            message.chat.id,
            document=filename,
            caption=caption
        )
        
        # Cleanup
        if os.path.exists(filename):
            os.remove(filename)
            
    except Exception as e:
        await message.reply_text(f"❌ **Error sending file:** `{str(e)}`")
