from typing import Any

from telethon import TelegramClient
from telethon.tl.functions import upload

from src.file_manager import FileManager
from src.logger import get_logger

logger = get_logger("executor")


class CommandExecutor:
    def __init__(self, tg_client: TelegramClient, file_manager: FileManager):
        self.tg_client = tg_client
        self.file_manager = file_manager

    async def execute(self, request_object: Any) -> str:
        """
        Executes a ready Telethon request object.
        """
        try:
            # Special handling for file uploads, as they are a two-step process
            if isinstance(request_object, upload.SaveFilePartRequest):
                # This part is complex and requires state (total parts, file id etc.)
                # For now, we assume the model knows how to construct this.
                # A better solution would be a dedicated 'upload_file' tool.
                pass

            result = await self.tg_client(request_object)
            return str(result)

        except Exception as e:
            # Any exception during execution is caught and re-raised.
            # The assistant will handle logging and reporting to the model.
            raise
