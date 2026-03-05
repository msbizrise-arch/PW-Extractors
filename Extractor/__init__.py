import nest_asyncio
nest_asyncio.apply()  # Fix Render event loop

from pyromod import Client
from config import API_ID, API_HASH, BOT_TOKEN

app = Client(
    "PWExtractor",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)
