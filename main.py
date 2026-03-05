import os
import logging
import asyncio
import nest_asyncio
from flask import Flask, jsonify
from threading import Thread

# Apply nest_asyncio for Render compatibility
nest_asyncio.apply()

from pyrogram import idle
from Extractor import app as pyrogram_app
from Extractor.modules import ALL_MODULES
import importlib

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
LOGGER = logging.getLogger(__name__)

# Flask app for health check (keeps Render service alive)
flask_app = Flask(__name__)

@flask_app.route("/", methods=["GET"])
def health():
    return jsonify({
        "status": "PW-Extractor Bot is Online",
        "bot": "Physics Wallah Extractor",
        "version": "2.0"
    })

@flask_app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "alive"})

# Load all modules
LOGGER.info("Loading modules...")
for module in ALL_MODULES:
    try:
        importlib.import_module(f"Extractor.modules.{module}")
        LOGGER.info(f"Loaded module: {module}")
    except Exception as e:
        LOGGER.error(f"Failed to load module {module}: {e}")

async def start_bot():
    """Start the Pyrogram bot"""
    await pyrogram_app.start()
    LOGGER.info("=" * 50)
    LOGGER.info("🚀 PW-Extractor Bot Started Successfully!")
    LOGGER.info("=" * 50)
    LOGGER.info(f"Bot Username: {(await pyrogram_app.get_me()).username}")
    LOGGER.info("Send /start in Telegram to use the bot")
    LOGGER.info("=" * 50)
    await idle()

def run_flask():
    """Run Flask in separate thread"""
    port = int(os.getenv("PORT", "10000"))
    flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    # Start Flask in background thread
    LOGGER.info("Starting Flask health check server...")
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Run the bot in main thread
    LOGGER.info("Starting Telegram Bot...")
    asyncio.get_event_loop().run_until_complete(start_bot())
