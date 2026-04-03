import asyncio
import time
from typing import Tuple, Union

from google import genai
from google.genai import types
from google.genai.types import HarmCategory, HarmBlockThreshold
from telethon import TelegramClient, errors

from src.buffer import EventBuffer
from src.config import (TG_API_ID, TG_API_HASH, SESSION_FILE, GEMINI_API_KEY, SYSTEM_PROMPT_PATH, PERSON_PROMPT_PATH)
from src.context import ContextManager
from src.executor import CommandExecutor
from src.logger import get_logger
from src.parser import parse_command

logger = get_logger("assistant")

REQUEST_INTERVAL = 5

SAFETY_SETTINGS = [
    types.SafetySetting(category=HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=HarmBlockThreshold.OFF),
    types.SafetySetting(category=HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=HarmBlockThreshold.OFF),
    types.SafetySetting(category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=HarmBlockThreshold.OFF),
    types.SafetySetting(category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=HarmBlockThreshold.OFF), ]


class TelegramAIAssistant:
    def __init__(self):
        try:
            self.tg_client = TelegramClient(SESSION_FILE, TG_API_ID, TG_API_HASH)
            self.genai_client = genai.Client(api_key=GEMINI_API_KEY, http_options={'api_version': 'v1beta'})

            if not SYSTEM_PROMPT_PATH.exists():
                raise FileNotFoundError(f"System prompt file not found at {SYSTEM_PROMPT_PATH}")

            system_prompt_content = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()

            person_prompt_content = ""
            if PERSON_PROMPT_PATH.exists():
                person_prompt_content = PERSON_PROMPT_PATH.read_text(encoding="utf-8").strip()
            else:
                logger.warning(f"Person prompt file not found at {PERSON_PROMPT_PATH}. Continuing without it.")

            combined_prompt_text = system_prompt_content
            if person_prompt_content:
                combined_prompt_text += "\n\nPERSON:\n" + person_prompt_content

            self.context_mgr = ContextManager(combined_prompt_text)
            self.executor = CommandExecutor(self.tg_client, self.genai_client)
            self.event_buffer = EventBuffer(self._on_event_buffer_flush)
            self._processing = False
            self._last_request_time = 0
            self.is_running = True
        except Exception as e:
            logger.critical(f"Failed to initialize assistant: {e}")
            self.is_running = False

    async def setup(self):
        try:
            await self.tg_client.start()
            self.tg_client.add_event_handler(self._raw_handler)
            logger.info("Started and connected to Telegram.")
            return True
        except errors.ApiIdInvalidError:
            logger.critical("Telegram API ID/Hash is invalid.")
        except Exception as e:
            logger.critical(f"Failed to connect to Telegram: {e}")
        return False

    async def _raw_handler(self, event):
        event_str = str(event)
        logger.info(event_str)
        self.event_buffer.add_event(event_str)

    async def _on_event_buffer_flush(self, events_list: list[str]):
        if self._processing:
            self.event_buffer.buffer.extend(events_list)
            return

        self._processing = True
        try:
            self.context_mgr.add_user_message("\n".join(events_list))
            await self._main_loop()
        except Exception as e:
            logger.error(f"Error in main processing loop: {e}", exc_info=True)
        finally:
            self._processing = False

    async def _main_loop(self):
        current_time = time.monotonic()
        time_since_last_request = current_time - self._last_request_time
        if time_since_last_request < REQUEST_INTERVAL:
            await asyncio.sleep(REQUEST_INTERVAL - time_since_last_request)

        self._last_request_time = time.monotonic()
        logger.info("Sending event batch to the neural network...")

        try:
            response = await self.genai_client.aio.models.generate_content(model="gemini-3.1-flash-lite-preview",
                                                                           contents=self.context_mgr.get_contents(),
                                                                           config=types.GenerateContentConfig(
                                                                               system_instruction=self.context_mgr.get_system_prompt(),
                                                                               safety_settings=SAFETY_SETTINGS, ))
            model_reply = response.text.strip()
        except Exception as e:
            logger.error(f"Neural network API call failed: {e}")
            return

        if not model_reply or model_reply.upper() == "NONE":
            logger.info("Neural network returned no actionable response.")
            return

        logger.info("Neural network response:\n%s", model_reply)
        self.context_mgr.add_model_message(model_reply)

        command_lines = [l.strip() for l in model_reply.split("\n") if l.strip()]
        if not command_lines:
            return

        logger.info("Executing commands...")
        has_executed_anything = False
        for line in command_lines:
            if line.upper() == "NONE":
                continue

            res_text: str = ""
            file_part: types.Part = None
            try:
                command_object = parse_command(line)
                execution_result: Union[str, Tuple[str, types.Part]] = await self.executor.execute(command_object)

                if isinstance(execution_result, tuple):
                    res_text, file_part = execution_result
                else:
                    res_text = execution_result
            except Exception as e:
                error_message = f"{type(e).__name__}: {e}"
                logger.error(f"Error processing command '{line}': {error_message}")
                res_text = error_message
                file_part = None

            formatted_result = f"{line}\n\n{res_text}"
            self.context_mgr.add_user_message(formatted_result, file_part=file_part)
            has_executed_anything = True

        if has_executed_anything:
            if self.event_buffer.buffer:
                new_events = "\n".join(self.event_buffer.buffer)
                self.event_buffer.buffer.clear()
                self.context_mgr.add_user_message(new_events)
            await self._main_loop()

    async def run(self):
        if not self.is_running or not await self.setup():
            return

        logger.info("Assistant is running. Press Ctrl+C to stop.")
        try:
            await self.tg_client.run_until_disconnected()
        finally:
            logger.info("Shutting down.")
            self.is_running = False
