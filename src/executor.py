import asyncio
from typing import Any, Dict, List, Optional, Tuple

from google.genai import types
from telethon import TelegramClient

from src.file_manager import FileManager


class CommandExecutor:
    def __init__(self, tg_client: TelegramClient, file_manager: FileManager):
        self.tg_client = tg_client
        self.file_manager = file_manager

    async def download_media(self, entity: Any, message_id: int) -> str:
        try:
            entity_resolved = await self.tg_client.get_input_entity(entity)
            msg = await self.tg_client.get_messages(entity_resolved, ids=int(message_id))
            if not msg or not msg.media:
                return "No media found in this message."
            path = await self.tg_client.download_media(msg, file="downloads/")
            return path if path else "Failed to download media."
        except Exception as e:
            return f"Error during download: {e}"

    async def execute(self, method_name: str, args: List[Any], kwargs: Dict[str, Any]) -> Tuple[
        str, str, Optional[types.Part]]:
        command_str = f"{method_name}({', '.join(map(repr, args))}, {', '.join(f'{k}={repr(v)}' for k, v in kwargs.items())})"

        try:
            if method_name == "download_media":
                result = await self.download_media(*args, **kwargs)
            else:
                method = getattr(self.tg_client, method_name, None)
                if not method or not callable(method):
                    raise AttributeError(f"Method '{method_name}' not found on TelegramClient.")

                if asyncio.iscoroutinefunction(method):
                    result = await method(*args, **kwargs)
                else:
                    result = method(*args, **kwargs)

            file_part = None
            if method_name == "download_media" and isinstance(result, str) and "/" in result:
                file_part = await self.file_manager.upload_and_get_part(result)

            return command_str, str(result), file_part

        except Exception as e:
            return command_str, f"Error: {e}", None
