from typing import Any

from telethon import TelegramClient

from src.logger import get_logger

logger = get_logger("executor")


class CommandExecutor:
    def __init__(self, tg_client: TelegramClient):
        self.tg_client = tg_client

    async def execute(self, request_object: Any) -> str:
        try:
            if request_object is None:
                # Return the string representation of None, as Python would.
                return "None"
            result = await self.tg_client(request_object)
            return str(result)
        except Exception as e:
            # Return the raw, "pure" error message from Python.
            error_message = f"{type(e).__name__}: {e}"
            logger.error(f"Error executing command: {error_message}")
            return error_message
