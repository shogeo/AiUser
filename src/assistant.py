import asyncio
import re
from typing import List, Optional, Tuple

from telethon import TelegramClient, events
from google import genai
from google.genai import types
from google.genai.types import HarmCategory, HarmBlockThreshold
from google.genai.errors import APIError

from src.config import (
    TG_API_ID, TG_API_HASH, SESSION_FILE,
    GEMINI_API_KEY, PROXYAPI_KEY, USE_PROXYAPI,
    SYSTEM_PROMPT_PATH
)
from src.logger import setup_logger
from src.buffer import EventBuffer
from src.context import ContextManager
from src.parser import parse_command
from src.file_manager import FileManager
from src.executor import CommandExecutor

logger = setup_logger(__name__)

if not SYSTEM_PROMPT_PATH.exists():
    raise FileNotFoundError(f"Системный промт не найден: {SYSTEM_PROMPT_PATH}")
SYSTEM_PROMPT = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")

# Настройки для отключения цензуры
SAFETY_SETTINGS = [
    types.SafetySetting(category=HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=HarmBlockThreshold.BLOCK_NONE),
    types.SafetySetting(category=HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=HarmBlockThreshold.BLOCK_NONE),
    types.SafetySetting(category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=HarmBlockThreshold.BLOCK_NONE),
    types.SafetySetting(category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=HarmBlockThreshold.BLOCK_NONE),
]

class TelegramAIAssistant:
    def __init__(self):
        self.tg_client: Optional[TelegramClient] = None
        self.genai_client: Optional[genai.Client] = None
        self.context_mgr = ContextManager(SYSTEM_PROMPT)
        self.file_manager: Optional[FileManager] = None
        self.executor: Optional[CommandExecutor] = None
        self.event_buffer: Optional[EventBuffer] = None
        self._processing = False

    async def setup(self):
        self.tg_client = TelegramClient(SESSION_FILE, TG_API_ID, TG_API_HASH)
        await self.tg_client.start()
        logger.info("Telethon client started.")

        if USE_PROXYAPI:
            self.genai_client = genai.Client(api_key=PROXYAPI_KEY, http_options={"base_url": "https://api.proxyapi.ru/google"}).aio
            logger.info("Gemini client initialized with ProxyAPI.")
        else:
            self.genai_client = genai.Client(api_key=GEMINI_API_KEY).aio
            logger.info("Gemini client initialized with official API.")

        self.file_manager = FileManager(self.genai_client)
        self.executor = CommandExecutor(self.tg_client, self.file_manager)
        self.event_buffer = EventBuffer(self._on_event_buffer_flush)

        @self.tg_client.on(events.Raw)
        async def raw_handler(update):
            logger.info("RAW EVENT: %s", type(update).__name__)
            logger.debug("Full raw event: %s", repr(update))

            event_str = repr(update)
            if self._processing:
                self.event_buffer.buffer.append(event_str)
                logger.debug("Event buffered during processing.")
            else:
                self.event_buffer.add_event(event_str)
                logger.debug("Event added to buffer.")

    async def _on_event_buffer_flush(self, events: List[str]):
        if not events:
            return
        if self._processing:
            logger.warning("Already processing, buffering new events from flush.")
            self.event_buffer.buffer.extend(events)
            return

        self._processing = True
        try:
            logger.info("Buffer flushed, processing %d events.", len(events))
            events_text = "\n".join(events)
            self.context_mgr.add_user_message(events_text)
            await self._main_loop()
        finally:
            self._processing = False
            if self.event_buffer.buffer:
                await self.event_buffer.force_flush()

    async def _main_loop(self):
        try:
            contents = self.context_mgr.get_contents()
            logger.debug("Sending %d messages to Gemini.", len(contents))
            
            # Правильный способ передачи safety_settings
            config = types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                safety_settings=SAFETY_SETTINGS
            )

            response = await self.genai_client.models.generate_content(
                model="gemini-3.1-flash-lite-preview",
                contents=contents,
                config=config
            )

            if not response.text:
                logger.warning("Gemini returned an empty response. Waiting for next event.")
                self._add_buffered_events_to_context()
                return

            model_reply = response.text.strip()
            self.context_mgr.add_model_message(model_reply)
            logger.info("Gemini response received:\n%s", model_reply)

            command_lines = [line.strip() for line in model_reply.split("\n") if line.strip()]
            outputs = []
            if command_lines and command_lines != ["None"]:
                for line in command_lines:
                    try:
                        method_name, args, kwargs = parse_command(line)
                        logger.info("Executing command: %s", method_name)
                        result = await self.executor.execute(method_name, args, kwargs)
                        if result:
                            outputs.append(result)
                    except Exception as e:
                        logger.error("Failed to parse command '%s': %s", line, e)
                        outputs.append((f"{line}", f"Ошибка парсинга: {e}", None))
            
            if outputs:
                self._process_execution_results(outputs)
            
            self._add_buffered_events_to_context()

            if outputs:
                 await self._main_loop()
        except APIError as e:
            logger.error("Gemini API error: %s", e)
            if "429" in str(e):
                match = re.search(r'retryDelay["\']:\s*["\']?(\d+)s', str(e))
                delay = int(match.group(1)) if match else 30
                logger.warning("Rate limit exceeded. Waiting %d seconds before retry.", delay)
                await asyncio.sleep(delay)
                await self._main_loop()
        except Exception as e:
            logger.exception("An unexpected error occurred in the main loop: %s", e)

    def _process_execution_results(self, outputs: List[Tuple[str, Optional[str], Optional[types.Part]]]):
        logger.info("Processing %d execution results.", len(outputs))
        for command_str, output_text, file_part in outputs:
            msg_lines = [command_str]
            if output_text is not None:
                msg_lines.append("")
                msg_lines.append(output_text)
            
            full_output_text = "\n".join(msg_lines)

            if file_part:
                self.context_mgr.history.append(
                    types.Content(role="user", parts=[types.Part.from_text(text=full_output_text), file_part])
                )
                logger.debug("Added user message with attached file part.")
            else:
                self.context_mgr.add_user_message(full_output_text)
                logger.debug("Added user text message: %s...", full_output_text[:70])

    def _add_buffered_events_to_context(self):
        if self.event_buffer.buffer:
            count = len(self.event_buffer.buffer)
            events = self.event_buffer.buffer.copy()
            self.event_buffer.buffer.clear()
            events_text = "\n".join(events)
            self.context_mgr.add_user_message(events_text)
            logger.info("Added %d buffered events to context.", count)

    async def run(self):
        await self.setup()
        logger.info("Assistant started. Press Ctrl+C to stop.")
        try:
            await self.tg_client.run_until_disconnected()
        except KeyboardInterrupt:
            logger.info("Stopping assistant by user request (Ctrl+C).")
        finally:
            if self.tg_client.is_connected():
                await self.tg_client.disconnect()
            if self.genai_client:
                await self.genai_client.aclose()
            logger.info("Clients closed gracefully.")