import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from telethon import TelegramClient
from google.genai import types

from src.logger import setup_logger
from src.file_manager import FileManager

logger = setup_logger(__name__)

class CommandExecutor:
    def __init__(self, tg_client: TelegramClient, file_manager: FileManager):
        self.tg_client = tg_client
        self.file_manager = file_manager

    async def _resolve_argument(self, arg: Any) -> Any:
        """Рекурсивно разрешает аргументы, если они являются инструкциями по получению."""
        if isinstance(arg, dict) and '_resolve_' in arg:
            resolve_type = arg['_resolve_']
            logger.debug("Resolving argument: %s", arg)

            if resolve_type == 'message':
                msg_id = arg.get('id')
                entity = arg.get('entity')
                if not msg_id:
                    raise ValueError("Для разрешения 'message' требуется 'id'.")

                message_obj = await self.tg_client.get_messages(entity, ids=int(msg_id))
                if not message_obj:
                    raise FileNotFoundError(f"Could not resolve: message with ID {msg_id} not found.")
                logger.debug("Successfully resolved 'message' argument to Message object.")
                return message_obj

            elif resolve_type == 'entity':
                entity_id = arg.get('id')
                if not entity_id:
                    raise ValueError("Для разрешения 'entity' требуется 'id'.")
                entity_obj = await self.tg_client.get_entity(entity_id)
                logger.debug("Successfully resolved 'entity' argument to Entity object.")
                return entity_obj

            else:
                raise NotImplementedError(f"Resolve type '{resolve_type}' is not supported.")

        elif isinstance(arg, list):
            return [await self._resolve_argument(item) for item in arg]
        elif isinstance(arg, dict):
            return {k: await self._resolve_argument(v) for k, v in arg.items()}

        return arg

    async def _handle_file_result(self, result: Any, command_str: str) -> Tuple[str, Optional[str], Optional[types.Part]]:
        """Обрабатывает результат, который может быть файлом, и возвращает готовый Part."""
        file_data = None
        if isinstance(result, (str, Path)) and Path(result).exists():
            file_data = Path(result)
        elif isinstance(result, bytes):
            file_data = result

        if file_data is not None:
            file_part = await self.file_manager.upload_and_get_part(file_data)
            if file_part:
                logger.info("File result processed and Part created successfully.")
                return (command_str, None, file_part)
            else:
                error_msg = "Failed to upload file to Gemini."
                logger.error(error_msg)
                return (command_str, error_msg, None)

        output_text = str(result) if result is not None else "Command returned no result."
        return (command_str, output_text, None)

    async def execute(self, method_name: str, args: List[Any], kwargs: Dict[str, Any]) -> Tuple[str, Optional[str], Optional[types.Part]]:
        """Выполняет команду Telethon и возвращает результат, включая готовый Part для файлов."""
        command_str = f"{method_name}({', '.join(map(repr, args))}, {', '.join(f'{k}={repr(v)}' for k, v in kwargs.items())})"
        logger.debug("Attempting to execute command: %s", command_str)

        try:
            resolved_args = [await self._resolve_argument(arg) for arg in args]
            resolved_kwargs = {k: await self._resolve_argument(v) for k, v in kwargs.items()}

            method_owner = resolved_args[0] if resolved_args and not isinstance(resolved_args[0], (str, int, float, bool, bytes)) else self.tg_client
            method = getattr(method_owner, method_name, None)

            if not callable(method):
                 method = getattr(self.tg_client, method_name, None)
                 if not callable(method):
                      raise AttributeError(f"Method '{method_name}' not found on client or resolved object.")
                 final_args = resolved_args
            else:
                 final_args = resolved_args[1:] if method_owner is not self.tg_client else resolved_args

            logger.info("Executing resolved command: %s", method_name)
            if asyncio.iscoroutinefunction(method):
                result = await method(*final_args, **resolved_kwargs)
            elif hasattr(method, '__aiter__'):
                result = b''.join([chunk async for chunk in method(*final_args, **resolved_kwargs)])
            else:
                result = method(*final_args, **resolved_kwargs)
            logger.info("Command '%s' executed successfully.", method_name)

            if isinstance(result, (str, Path, bytes)):
                return await self._handle_file_result(result, command_str)

            output_text = str(result) if result is not None else "Command executed without a return value."
            return (command_str, output_text, None)

        except Exception as e:
            logger.exception("Failed to execute command '%s': %s", command_str, e)
            return (command_str, f"Execution error: {e}", None)