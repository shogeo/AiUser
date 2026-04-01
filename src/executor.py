from typing import Any

from telethon import TelegramClient

from src.logger import get_logger

logger = get_logger("executor")


class CommandExecutor:
    def __init__(self, tg_client: TelegramClient):
        self.tg_client = tg_client

    async def execute(self, request_object: Any) -> str:
        result = await self.tg_client(request_object)
        return str(result)
