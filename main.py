import asyncio

from src.assistant import TelegramAIAssistant


async def main():
    assistant = TelegramAIAssistant()
    await assistant.run()


if __name__ == "__main__":
    asyncio.run(main())
