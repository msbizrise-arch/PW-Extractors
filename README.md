# 🎓 PW-Extractor Bot

**Physics Wallah Content Extractor Telegram Bot**

Extract videos (M3U8), notes (PDFs), and DPPs from Physics Wallah batches with ease!

---

## ✨ Features

- 🔐 **Login Methods:** Mobile + OTP or Direct Token
- 📹 **Video Extraction:** Get M3U8 streaming links
- 📄 **Notes Extraction:** Download PDF links
- 📚 **Batch & Subject Selection:** Choose what you want
- 💎 **Premium System:** Admin-controlled premium access
- 📊 **Admin Panel:** Manage users and view stats

---

## 🚀 Deployment on Render (Free)

### Step 1: Fork/Clone this Repository
```bash
git clone https://github.com/yourusername/PW-Extractor.git
```

### Step 2: Create Render Account
1. Go to [render.com](https://render.com)
2. Sign up with GitHub
3. Click "New Web Service"
4. Connect your repository

### Step 3: Configure Build Settings
```
Build Command: pip install -r requirements.txt
Start Command: bash start.sh
```

### Step 4: Add Environment Variables

| Variable | Description | How to Get |
|----------|-------------|------------|
| `API_ID` | Telegram API ID | [my.telegram.org](https://my.telegram.org) |
| `API_HASH` | Telegram API Hash | [my.telegram.org](https://my.telegram.org) |
| `BOT_TOKEN` | Bot Token | [@BotFather](https://t.me/BotFather) |
| `OWNER_ID` | Your Telegram ID | [@userinfobot](https://t.me/userinfobot) |
| `MONGO_URL` | MongoDB URL | [MongoDB Atlas](https://www.mongodb.com/atlas) |
| `CHANNEL_ID` | Force Sub Channel ID | Create a channel, add bot as admin |
| `PREMIUM_LOGS` | Logs Channel ID | Optional - for premium logs |
| `SUDO_USERS` | Admin User IDs | Space-separated list |

### Step 5: Deploy!
Click "Create Web Service" and wait for deployment.

---

## 🔧 Local Setup

### Prerequisites
- Python 3.12+
- MongoDB (local or Atlas)

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/PW-Extractor.git
cd PW-Extractor

# Create virtual environment
python -m venv venv

# Activate (Linux/Mac)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp config.py .env
# Edit .env with your credentials

# Run bot
python main.py
```

---

## 📋 Commands

### User Commands
| Command | Description |
|---------|-------------|
| `/start` | Start the bot |
| `/myplan` | Check premium status |

### Admin Commands
| Command | Description |
|---------|-------------|
| `/addpremium user_id duration` | Add premium (e.g., 7days, 1month) |
| `/removepremium user_id` | Remove premium |
| `/checkpremium user_id` | Check user's premium |
| `/premiumusers` | List all premium users |
| `/stats` | Bot statistics |

---

## 🔑 Getting Credentials

### 1. Telegram API (API_ID & API_HASH)
1. Visit [my.telegram.org](https://my.telegram.org)
2. Login with your phone number
3. Go to "API Development Tools"
4. Create a new application
5. Copy `api_id` and `api_hash`

### 2. Bot Token
1. Message [@BotFather](https://t.me/BotFather)
2. Send `/newbot`
3. Follow instructions
4. Copy the bot token

### 3. MongoDB URL
1. Sign up at [MongoDB Atlas](https://www.mongodb.com/atlas)
2. Create a free cluster
3. Go to Database Access → Create User
4. Go to Network Access → Add IP `0.0.0.0/0`
5. Click Connect → Drivers → Python
6. Copy the connection string

### 4. Channel ID
1. Create a Telegram channel
2. Add your bot as administrator
3. Send a message in the channel
4. Forward it to [@userinfobot](https://t.me/userinfobot)
5. Copy the ID (starts with `-100`)

---

## 📁 Project Structure

```
PW-Extractor/
├── Extractor/
│   ├── __init__.py          # Pyrogram Client
│   ├── core/
│   │   ├── func.py          # Helper functions
│   │   ├── script.py        # Bot messages
│   │   └── mongo/
│   │       └── plans_db.py  # Database functions
│   └── modules/
│       ├── __init__.py      # Module list
│       ├── start.py         # Start command
│       ├── pw.py            # PW extraction
│       └── plans.py         # Premium system
├── config.py                # Configuration
├── main.py                  # Entry point
├── start.sh                 # Startup script
├── requirements.txt         # Dependencies
├── Procfile                 # Render config
├── render.yaml              # Render blueprint
└── README.md                # This file
```

---

## ⚠️ Important Notes

1. **Token Security:** Never share your `BOT_TOKEN` or `API_HASH`
2. **Rate Limits:** Don't extract too fast to avoid IP bans
3. **Legal:** Use responsibly and respect copyright laws
4. **Premium:** Set `SUDO_USERS` to manage premium users

---

## 🐛 Troubleshooting

### Bot not responding?
- Check if all env variables are set
- Verify `BOT_TOKEN` is correct
- Check Render logs for errors

### MongoDB connection failed?
- Verify `MONGO_URL` is correct
- Check if IP whitelist includes `0.0.0.0/0`
- Ensure database user has correct password

### Extraction not working?
- Check if token is valid
- Verify batch has active content
- Try using Mobile + OTP method

---

## 📞 Support

For support, contact the admin or create an issue on GitHub.

---

## 📜 License

This project is for educational purposes only.

---

**Made with ❤️ for Physics Wallah Students**
