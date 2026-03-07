import os
import logging
import threading
import asyncio

from flask import Flask, jsonify
from pyrogram import idle

from Extractor import app as pyrogram_app
from Extractor.modules import ALL_MODULES
import importlib

logging.basicConfig(level=logging.INFO, format="%(name)s - %(message)s")
LOGGER = logging.getLogger(__name__)

flask_app = Flask(__name__)

# Load all handler modules
for module in ALL_MODULES:
    importlib.import_module(f"Extractor.modules.{module}")
    LOGGER.info(f"Loaded module: {module}")


@flask_app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "PW-Extractor Online"})


def run_flask():
    """Run Flask server for Render health checks."""
    port = int(os.getenv("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


async def start_bot():
    """Start the Pyrogram bot client via MTProto polling."""
    await pyrogram_app.start()
    LOGGER.info("Bot started successfully via MTProto polling!")
    await idle()
    await pyrogram_app.stop()


if __name__ == "__main__":
    # Start Flask in a daemon thread for Render health checks
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    LOGGER.info("Flask health-check server started")

    # Run the Pyrogram bot in the main thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_bot())
