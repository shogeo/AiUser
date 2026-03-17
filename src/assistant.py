import asyncio
from telethon import TelegramClient, events
from google import genai
from google.genai import types
from google.genai.types import HarmCategory, HarmBlockThreshold
from src.config import (
    TG_API_ID, TG_API_HASH, SESSION_FILE,
    GEMINI_API_KEY, SYSTEM_PROMPT_PATH
)
from src.logger import setup_logger
from src.buffer import EventBuffer
from src.context import ContextManager
from src.parser import parse_command
from src.file_manager import FileManager
from src.executor import CommandExecutor

logger = setup_logger(__name__)

# Отключение цензуры
SAFETY_SETTINGS = [
    types.SafetySetting(category=HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=HarmBlockThreshold.BLOCK_NONE),
    types.SafetySetting(category=HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=HarmBlockThreshold.BLOCK_NONE),
    types.SafetySetting(category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=HarmBlockThreshold.BLOCK_NONE),
    types.SafetySetting(category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=HarmBlockThreshold.BLOCK_NONE),
]

class TelegramAIAssistant:
    def __init__(self):
        self.tg_client = TelegramClient(SESSION_FILE, TG_API_ID, TG_API_HASH)
        # Версия v1beta для новых фишек
        self.genai_client = genai.Client(api_key=GEMINI_API_KEY, http_options={'api_version': 'v1beta'})
        
        if not SYSTEM_PROMPT_PATH.exists():
            raise FileNotFoundError(f"Prompt file missing: {SYSTEM_PROMPT_PATH}")
        prompt_text = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
        
        self.context_mgr = ContextManager(prompt_text)
        self.file_manager = FileManager(self.genai_client)
        self.executor = CommandExecutor(self.tg_client, self.file_manager)
        
        self.event_buffer = EventBuffer(self._on_event_buffer_flush)
        self._processing = False
        logger.info("Assistant initialized with model gemini-3.1-flash-lite-preview")

    async def setup(self):
        await self.tg_client.start()
        self.tg_client.add_event_handler(self._raw_handler)
        logger.info("Telegram client started.")

    async def _raw_handler(self, event):
        logger.debug("New raw event: %s", type(event).__name__)
        self.event_buffer.add_event(str(event))

    async def _on_event_buffer_flush(self, events_list: list[str]):
        if self._processing:
            logger.info("AI is currently busy. Buffering %d events.", len(events_list))
            self.event_buffer.buffer.extend(events_list)
            return

        self._processing = True
        logger.info("Processing %d events from buffer.", len(events_list))
        try:
            self.context_mgr.add_user_message("\n".join(events_list))
            await self._main_loop()
        finally:
            self._processing = False

    async def _main_loop(self):
        try:
            logger.info("Requesting Gemini (gemini-3.1-flash-lite-preview)...")
            response = await self.genai_client.aio.models.generate_content(
                model="gemini-3.1-flash-lite-preview",
                contents=self.context_mgr.get_contents(),
                config=types.GenerateContentConfig(
                    safety_settings=SAFETY_SETTINGS,
                    temperature=0.7
                )
            )

            if not response.text:
                logger.warning("Gemini returned no text. Breaking loop.")
                return
            
            model_reply = response.text.strip()
            logger.info("Model response received: %s", model_reply)
            
            # ЖЕСТКАЯ ПРОВЕРКА НА ВЫХОД
            if model_reply.upper() == "NONE":
                logger.info("AI signaled completion with 'None'. Loop terminated.")
                return

            self.context_mgr.add_model_message(model_reply)
            command_lines = [l.strip() for l in model_reply.split("\n") if l.strip()]
            
            has_executed_anything = False
            for line in command_lines:
                if line.upper() == "NONE":
                    continue
                
                try:
                    logger.info("Parsing & Executing: %s", line)
                    method, args, kwargs = parse_command(line)
                    cmd_str, res_text, file_part = await self.executor.execute(method, args, kwargs)
                    
                    logger.info("Result of %s: %s", method, str(res_text)[:100])
                    # Сразу пушим результат выполнения в контекст
                    self.context_mgr.add_user_message(f"{cmd_str}\n\n{res_text}", file_part=file_part)
                    has_executed_anything = True
                except Exception as e:
                    logger.error("Execution failed for '%s': %s", line, e)
                    self.context_mgr.add_user_message(f"{line}\n\nError: {e}")

            if has_executed_anything:
                # Если пока мы работали, упали новые сообщения - закидываем их в контекст
                if self.event_buffer.buffer:
                    new_events = "\n".join(self.event_buffer.buffer)
                    logger.info("Adding %d new events from buffer to current loop.", len(self.event_buffer.buffer))
                    self.event_buffer.buffer.clear()
                    self.context_mgr.add_user_message(new_events)
                
                # Рекурсивный вызов для обработки результатов
                await self._main_loop()

        except Exception as e:
            logger.error("Fatal error in assistant loop: %s", e, exc_info=True)

    async def run(self):
        await self.setup()
        logger.info("Assistant running. Press Ctrl+C to exit.")
        await self.tg_client.run_until_disconnected()

