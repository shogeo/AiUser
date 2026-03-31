from google import genai
from google.genai import types
from google.genai.types import HarmCategory, HarmBlockThreshold
from telethon import TelegramClient

from src.buffer import EventBuffer
from src.config import (TG_API_ID, TG_API_HASH, SESSION_FILE, GEMINI_API_KEY, SYSTEM_PROMPT_PATH)
from src.context import ContextManager
from src.executor import CommandExecutor
from src.file_manager import FileManager
from src.logger import setup_logger
from src.parser import parse_command

logger = setup_logger("assistant")

SAFETY_SETTINGS = [
    types.SafetySetting(category=HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=HarmBlockThreshold.BLOCK_NONE),
    types.SafetySetting(category=HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=HarmBlockThreshold.BLOCK_NONE),
    types.SafetySetting(category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=HarmBlockThreshold.BLOCK_NONE),
    types.SafetySetting(category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                        threshold=HarmBlockThreshold.BLOCK_NONE), ]


class TelegramAIAssistant:
    def __init__(self):
        self.tg_client = TelegramClient(SESSION_FILE, TG_API_ID, TG_API_HASH)
        self.genai_client = genai.Client(api_key=GEMINI_API_KEY, http_options={'api_version': 'v1beta'})

        if not SYSTEM_PROMPT_PATH.exists():
            raise FileNotFoundError(f"Prompt file missing: {SYSTEM_PROMPT_PATH}")
        prompt_text = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")

        self.context_mgr = ContextManager(prompt_text)
        self.file_manager = FileManager(self.genai_client)
        self.executor = CommandExecutor(self.tg_client, self.file_manager)

        self.event_buffer = EventBuffer(self._on_event_buffer_flush)
        self._processing = False

    async def setup(self):
        await self.tg_client.start()
        self.tg_client.add_event_handler(self._raw_handler)
        logger.info("Assistant started and connected to Telegram.")

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
        finally:
            self._processing = False

    async def _main_loop(self):
        try:
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

                try:
                    method, args, kwargs = parse_command(line)
                    cmd_str, res_text, file_part = await self.executor.execute(method, args, kwargs)
                    self.context_mgr.add_user_message(f"{cmd_str}\n\n{res_text}", file_part=file_part)
                    has_executed_anything = True
                except Exception as e:
                    logger.error("Failed to execute command '%s': %s", line, e)
                    self.context_mgr.add_user_message(f"Error executing command:\n{line}\n\n{e}")

            if has_executed_anything:
                if self.event_buffer.buffer:
                    new_events = "\n".join(self.event_buffer.buffer)
                    self.event_buffer.buffer.clear()
                    self.context_mgr.add_user_message(new_events)
                
                await self._main_loop()

        except Exception as e:
            logger.critical("Fatal error in main loop: %s", e, exc_info=True)

    async def run(self):
        await self.setup()
        await self.tg_client.run_until_disconnected()
