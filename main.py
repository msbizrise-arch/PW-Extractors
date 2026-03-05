import os
import logging
import threading

import requests as http_requests
from flask import Flask, jsonify

from config import BOT_TOKEN
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


def delete_webhook():
    """Delete any existing Bot API webhook so MTProto polling works."""
    if not BOT_TOKEN:
        return
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook?drop_pending_updates=false"
        resp = http_requests.get(url, timeout=10).json()
        LOGGER.info(f"deleteWebhook response: {resp}")
        # Also verify with getWebhookInfo
        info_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo"
        info = http_requests.get(info_url, timeout=10).json()
        LOGGER.info(f"getWebhookInfo: {info}")
    except Exception as e:
        LOGGER.error(f"Failed to delete webhook: {e}")


if __name__ == "__main__":
    # Delete any leftover webhook from previous deployments
    delete_webhook()

    # Start Flask in a daemon thread for Render health checks
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    LOGGER.info("Flask health-check server started")

    # Run the Pyrogram bot using its built-in run() method
    # This properly handles event loop, signals, and cleanup
    LOGGER.info("Starting Pyrogram bot...")
    pyrogram_app.run()
