import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from google.genai import types
from telethon import TelegramClient

from src.exceptions import CommandNotFoundError, InvalidArgumentError, SystemCommandError, FileOperationError
from src.file_manager import FileManager
from src.logger import get_logger

logger = get_logger("executor")


@dataclass
class CommandResult:
    text_result: str
    file_to_upload: Optional[Path] = None


class CommandExecutor:
    def __init__(self, tg_client: TelegramClient, file_manager: FileManager):
        self.tg_client = tg_client
        self.file_manager = file_manager

    async def download_media(self, entity: Union[int, str], message_id: int) -> CommandResult:
        try:
            entity_resolved = await self.tg_client.get_input_entity(entity)
            msg = await self.tg_client.get_messages(entity_resolved, ids=int(message_id))
            if not msg or not msg.media:
                return CommandResult(text_result="No media found in this message.")

            path = await self.tg_client.download_media(msg, file=str(self.file_manager.downloads_dir))

            if path:
                downloaded_path = Path(path)
                return CommandResult(text_result=f"Media downloaded to {downloaded_path.name}",
                                     file_to_upload=downloaded_path)
            else:
                raise FileOperationError("Failed to download media: unknown reason.")
        except FileOperationError:
            raise
        except Exception as e:
            logger.error("System error during media download for entity '%s', message_id '%s': %s", entity, message_id,
                         e, exc_info=True)
            raise SystemCommandError(f"System error during media download: {e}") from e

    async def download_profile_photo(self, entity: Union[int, str], download_big: bool = True) -> CommandResult:
        try:
            entity_resolved = await self.tg_client.get_input_entity(entity)
            path = await self.tg_client.download_profile_photo(entity_resolved,
                                                               file=str(self.file_manager.downloads_dir),
                                                               download_big=download_big)

            if path:
                downloaded_path = Path(path)
                return CommandResult(text_result=f"Profile photo downloaded to {downloaded_path.name}",
                                     file_to_upload=downloaded_path)
            else:
                raise FileOperationError("Failed to download profile photo: unknown reason.")
        except FileOperationError:
            raise
        except Exception as e:
            logger.error("System error during profile photo download for entity '%s': %s", entity, e, exc_info=True)
            raise SystemCommandError(f"System error during profile photo download: {e}") from e

    async def execute(self, method_name: str, args: List[Any], kwargs: Dict[str, Any]) -> Tuple[
        str, str, Optional[types.Part]]:

        command_str = f"{method_name}({', '.join(map(repr, args))}, {', '.join(f'{k}={repr(v)}' for k, v in kwargs.items())})"

        try:
            command_result: CommandResult

            if method_name == "download_media":
                command_result = await self.download_media(*args, **kwargs)
            elif method_name == "download_profile_photo":
                command_result = await self.download_profile_photo(*args, **kwargs)
            else:
                method = getattr(self.tg_client, method_name, None)
                if not method or not callable(method):
                    raise CommandNotFoundError(f"Method '{method_name}' not found on TelegramClient.")

                try:
                    if asyncio.iscoroutinefunction(method):
                        raw_result = await method(*args, **kwargs)
                    else:
                        raw_result = method(*args, **kwargs)

                    command_result = CommandResult(text_result=str(raw_result))
                except TypeError as e:
                    raise InvalidArgumentError(f"Invalid arguments for method '{method_name}': {e}") from e
                except Exception as e:
                    logger.error("System error during execution of TelegramClient method '%s': %s", method_name, e,
                                 exc_info=True)
                    raise SystemCommandError(f"System error during execution of '{method_name}': {e}") from e

            file_part = None
            if command_result.file_to_upload:
                file_part = await self.file_manager.upload_and_get_part(command_result.file_to_upload)

            return command_str, command_result.text_result, file_part

        except (CommandNotFoundError, InvalidArgumentError, SystemCommandError, FileOperationError):
            raise
        except Exception as e:
            logger.critical("An unexpected error occurred in execute for command '%s': %s", command_str, e,
                            exc_info=True)
            raise SystemCommandError(f"An unexpected system error occurred during command execution: {e}") from e
