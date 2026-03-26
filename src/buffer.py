import asyncio
from typing import List, Optional, Callable, Awaitable

from src.config import EVENT_BUFFER_TIMEOUT


class EventBuffer:
    def __init__(self, flush_callback: Callable[[List[str]], Awaitable[None]]):
        self.buffer: List[str] = []
        self.flush_callback = flush_callback
        self._timer_task: Optional[asyncio.Task] = None

    def add_event(self, event_str: str):
        self.buffer.append(event_str)
        self._restart_timer()

    def _restart_timer(self):
        if self._timer_task:
            self._timer_task.cancel()
        self._timer_task = asyncio.create_task(self._timer())

    async def _timer(self):
        try:
            await asyncio.sleep(EVENT_BUFFER_TIMEOUT)
            await self._flush()
        except asyncio.CancelledError:
            pass

    async def _flush(self):
        if not self.buffer:
            return
        events_copy = self.buffer.copy()
        self.buffer.clear()
        self._timer_task = None
        await self.flush_callback(events_copy)

    async def force_flush(self):
        if self._timer_task:
            self._timer_task.cancel()
            self._timer_task = None
        if self.buffer:
            await self._flush()
