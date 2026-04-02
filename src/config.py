import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

TG_API_ID = int(os.getenv("TG_API_ID"))
TG_API_HASH = os.getenv("TG_API_HASH")
SESSION_FILE = "session.session"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

EVENT_BUFFER_TIMEOUT = 10

SYSTEM_PROMPT_PATH = Path("system_prompt.txt")
CONTEXT_FILE_PATH = Path("context.json")
