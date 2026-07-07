import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
KIE_API_KEY = os.getenv("KIE_API_KEY")

ADMIN_ID = int(os.getenv("ADMIN_ID", "6318606774"))
