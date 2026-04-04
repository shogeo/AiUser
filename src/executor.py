import asyncio
import os
from typing import Any, Dict, Tuple, Union

from google import genai
from google.genai import types
from telethon import TelegramClient
from telethon.errors import RPCError

from src.exceptions import MethodNotFoundError, ArgumentError, ExecutionError
from src.logger import get_logger

logger = get_logger("executor")


class CommandExecutor:
    def __init__(self, tg_client: TelegramClient, genai_client: genai.Client):
        self.tg_client = tg_client
        self.genai_client = genai_client

    async def _download_and_upload(self, download_coro) -> Tuple[str, types.Part]:
        download_path = "downloads/"
        os.makedirs(download_path, exist_ok=True)

        local_path = await download_coro(download_path)
        if not local_path or not os.path.exists(local_path):
            pass

        try:
            google_file = await self.genai_client.aio.files.upload(file=local_path)

            while google_file.state.name != "ACTIVE":
                if google_file.state.name == "FAILED":
                    raise ConnectionError(f"Google API file upload failed. Final state: {google_file}")
                await asyncio.sleep(1)
                google_file = await self.genai_client.aio.files.get(name=google_file.name)

            return str(local_path), types.Part.from_uri(file_uri=google_file.uri, mime_type=google_file.mime_type)
        finally:
            if os.path.exists(local_path):
                os.remove(local_path)

    async def execute(self, command: Dict[str, Any]) -> Union[str, Tuple[str, types.Part]]:
        try:
            command_type = command.get("type")

            if command_type == "high_level":
                method_name = command["method_name"]
                args = command.get("args", [])
                kwargs = command.get("kwargs", {})

                if method_name == "download_media":
                    chat_id = args[0]
                    message_id = kwargs["message_id"]
                    message = await self.tg_client.get_messages(chat_id, ids=message_id)
                    return await self._download_and_upload(lambda path: message.download_media(file=path))

                elif method_name == "download_profile_photo":
                    entity = await self.tg_client.get_entity(args[0])
                    return await self._download_and_upload(
                        lambda path: self.tg_client.download_profile_photo(entity, file=path))

                else:
                    method_to_call = getattr(self.tg_client, method_name)
                    result = await method_to_call(*args, **kwargs)

            elif command_type == "low_level":
                request_object = command.get("request_object")
                result = await self.tg_client(request_object)

            else:
                raise MethodNotFoundError(f"Unknown command type: {command_type}")

            return str(result) if result is not None else "None"

        except AttributeError as e:
            raise MethodNotFoundError(str(e)) from e
        except (TypeError, ValueError) as e:
            raise ArgumentError(str(e)) from e
        except RPCError as e:
            raise ExecutionError(f"{type(e).__name__}: {e}") from e
        except Exception as e:
            logger.error("Unhandled system exception in CommandExecutor: %s", e)
            return "SYSTEM_ERROR"
