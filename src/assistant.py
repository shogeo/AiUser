import asyncio
import time

from google import genai
from google.genai import types
from google.genai.types import HarmCategory, HarmBlockThreshold
from telethon import TelegramClient

from src.buffer import EventBuffer
from src.config import (TG_API_ID, TG_API_HASH, SESSION_FILE, GEMINI_API_KEY, SYSTEM_PROMPT_PATH)
from src.context import ContextManager
from src.executor import CommandExecutor
from src.logger import get_logger, configure_logging
from src.parser import parse_full_api_command

configure_logging()
logger = get_logger("assistant")

REQUEST_INTERVAL = 4

SAFETY_SETTINGS = [
    types.SafetySetting(category=HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=HarmBlockThreshold.OFF),
    types.SafetySetting(category=HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=HarmBlockThreshold.OFF),
    types.SafetySetting(category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=HarmBlockThreshold.OFF),
    types.SafetySetting(category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=HarmBlockThreshold.OFF), ]


class TelegramAIAssistant:
    def __init__(self):
        self.tg_client = TelegramClient(SESSION_FILE, TG_API_ID, TG_API_HASH)
        self.genai_client = genai.Client(api_key=GEMINI_API_KEY, http_options={'api_version': 'v1beta'})

        if not SYSTEM_PROMPT_PATH.exists():
            raise FileNotFoundError(f"Prompt file missing: {SYSTEM_PROMPT_PATH}")
        prompt_text = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")

        self.context_mgr = ContextManager(prompt_text)
        self.executor = CommandExecutor(self.tg_client)

        self.event_buffer = EventBuffer(self._on_event_buffer_flush)
        self._processing = False
        self._last_request_time = 0

    async def setup(self):
        await self.tg_client.start()
        self.tg_client.add_event_handler(self._raw_handler)
        logger.info("Started and connected to Telegram.")

    async def _raw_handler(self, event):
        event_str = str(event)
        logger.info(event_str)
        self.event_buffer.add_event(event_str)

    async def _on_event_buffer_flush(self, events_list: list[str]):
        if self._processing:
            self.event_buffer.buffer.extend(events_list)
            return

        self._processing = True
        self.context_mgr.add_user_message("\n".join(events_list))
        await self._main_loop()
        self._processing = False

    async def _main_loop(self):
        current_time = time.monotonic()
        time_since_last_request = current_time - self._last_request_time

        if time_since_last_request < REQUEST_INTERVAL:
            delay = REQUEST_INTERVAL - time_since_last_request
            logger.info(f"Waiting for {delay:.2f} seconds to respect the request interval...")
            await asyncio.sleep(delay)

        self._last_request_time = time.monotonic()
        logger.info("Sending event batch to the neural network...")
        response = await self.genai_client.aio.models.generate_content(model="gemini-3.1-flash-lite-preview",
                                                                       contents=self.context_mgr.get_contents(),
                                                                       config=types.GenerateContentConfig(
                                                                           system_instruction=self.context_mgr.get_system_prompt(),
                                                                           safety_settings=SAFETY_SETTINGS, ))

        if not response.text:
            logger.warning("Neural network returned no text. Ending loop.")
            return

        model_reply = response.text.strip()
        logger.info("Neural network response:\n%s", model_reply)

        if model_reply.upper() == "NONE":
            return

        self.context_mgr.add_model_message(model_reply)
        command_lines = [l.strip() for l in model_reply.split("\n") if l.strip()]

        if command_lines:
            logger.info("Executing commands and getting results...")

        has_executed_anything = False
        for line in command_lines:
            if line.upper() == "NONE":
                continue

            request_object = parse_full_api_command(line)
            res_text = await self.executor.execute(request_object)
            self.context_mgr.add_user_message(f"{line}\n\n{res_text}")
            has_executed_anything = True

        if has_executed_anything:
            if self.event_buffer.buffer:
                new_events = "\n".join(self.event_buffer.buffer)
                self.event_buffer.buffer.clear()
                self.context_mgr.add_user_message(new_events)

            await self._main_loop()

    async def run(self):
        await self.setup()
        await self.tg_client.run_until_disconnected()
        logger.info("Shutting down.")
