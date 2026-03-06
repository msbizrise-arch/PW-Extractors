# PW Extractor Bot - FIXED FILES

## Files Updated

| File | Description |
|------|-------------|
| `config.py` | Configuration with OWNER_ID=87xxxx2029 |
| `pw.py` | Main PW module - OTP, Token, Extraction |
| `plans.py` | Premium plans - Fixed database errors |
| `plans_db.py` | MongoDB functions - SSL fix |
| `start.py` | Start module - Fixed callbacks |

## Key Fixes Applied

### 1. MongoDB SSL Handshake Error (FIXED)
- Changed `tls=True` to `tls=False` in MongoDB connection
- This fixes the SSL handshake failed error on Render

### 2. MESSAGE_NOT_MODIFIED Error (FIXED)
- Added try-except blocks around all `edit_text()` calls
- Checks for "MESSAGE_NOT_MODIFIED" in error and handles gracefully

### 3. Premium Database Error (FIXED)
- Fixed collection truth value testing (`if db is None` instead of `if not db`)
- Better error handling in all database functions
- Proper initialization with fallback

### 4. OTP Not Sending (FIXED)
- Correct API endpoint: `/v3/users/get-otp`
- Proper headers with `client-id`, `client-type`, `client-version`
- Added `otpType: "login"` parameter

### 5. Token Validation (FIXED)
- Multiple endpoints tried for batch fetching
- Better error handling for expired tokens
- Token still works even if shows "expired"

### 6. Without Login Batches (FIXED)
- Keyword-based batch search working
- Proper filtering by batch name
- SN number selection working

### 7. Extraction Engine (FIXED)
- Videos, Notes, DPPs all extract properly
- CDN link conversion for encrypted links
- Proper file generation and sending

## How to Use These Files

1. Replace your existing files with these updated ones
2. Rename them back (remove 'ms' prefix) OR update imports
3. Set environment variables:
   ```
   OWNER_ID=8703802029
   MONGO_URL=your_mongodb_url
   PW_UNIVERSAL_TOKEN=your_token (optional)
   ```

## Commands Available

- `/start` - Start the bot
- `/help` - Show help
- `/myplan` - Check premium status
- `/add_premium <user_id> <time>` - Admin only
- `/remove_premium <user_id>` - Admin only
- `/chk_premium` - List all premium users (Admin)
- `/cancel` - Cancel current operation

## OWNER ID
Fixed to: **8703802029**
