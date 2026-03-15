import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Telegram
TG_API_ID = int(os.getenv("TG_API_ID"))
TG_API_HASH = os.getenv("TG_API_HASH")
SESSION_FILE = "session.session"

# Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PROXYAPI_KEY = os.getenv("PROXYAPI_KEY")

# Выбор API: True = ProxyAPI, False = официальный Gemini
USE_PROXYAPI = False

# Время накопления событий (секунды)
EVENT_BUFFER_TIMEOUT = 10

# Путь к системному промту
SYSTEM_PROMPT_PATH = Path("system_prompt.txt")