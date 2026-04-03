from typing import Any, Dict

from telethon import TelegramClient

from src.logger import get_logger

logger = get_logger("executor")


class CommandExecutor:
    def __init__(self, tg_client: TelegramClient):
        self.tg_client = tg_client

    async def execute(self, command: Dict[str, Any]) -> str:
        if not command:
            return "Invalid command object."

        command_type = command.get("type")

        try:
            if command_type == "high_level":
                method_name = command["method_name"]
                args = command.get("args", [])
                kwargs = command.get("kwargs", {})

                logger.info(f"Executing high-level command: client.{method_name}")
                method_to_call = getattr(self.tg_client, method_name)
                result = await method_to_call(*args, **kwargs)

            elif command_type == "low_level":
                request_object = command.get("request_object")
                if request_object is None:
                    return "No request object found for low-level command."

                logger.info(f"Executing low-level command: {request_object.__class__.__name__}")
                result = await self.tg_client(request_object)

            else:
                return f"Unknown command type: {command_type}"

            return str(result) if result is not None else "None"

        except Exception as e:
            error_message = f"{type(e).__name__}: {e}"
            logger.error(f"Error executing command {command}: {error_message}")
            return error_message
