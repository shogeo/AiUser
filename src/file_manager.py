import asyncio
from pathlib import Path
from typing import Optional, Union

from google import genai
from google.genai import types

from src.logger import setup_logger

logger = setup_logger(__name__)


class FileManager:
    def __init__(self, genai_client: genai.Client):
        self.genai_client = genai_client
        self.downloads_dir = Path("./downloads")
        self.downloads_dir.mkdir(exist_ok=True)
        logger.info("File manager initialized. Downloads directory is '%s'.", self.downloads_dir)

    def get_filename(self, file_data: Union[str, Path, bytes]) -> str:
        if isinstance(file_data, (str, Path)):
            return Path(file_data).name
        return f"temp_file_{hash(file_data)}.bin"

    async def upload_and_get_part(self, file_data: Union[str, Path, bytes]) -> Optional[types.Part]:
        filename = self.get_filename(file_data)
        try:
            if isinstance(file_data, (str, Path)):
                path_to_upload = Path(file_data)
                if not path_to_upload.exists():
                    logger.error("File not found: %s", path_to_upload)
                    return None
            else:
                path_to_upload = self.downloads_dir / filename
                path_to_upload.write_bytes(file_data)

            logger.info("Uploading '%s' to Gemini via Async API...", filename)
            # Используем .aio для асинхронности
            uploaded_file = await self.genai_client.aio.files.upload(file=path_to_upload)

            # Ожидание активации файла
            while uploaded_file.state.name != "ACTIVE":
                if uploaded_file.state.name == "FAILED":
                    logger.error("File processing FAILED in Gemini.")
                    return None
                logger.debug("Waiting for file activation (current: %s)...", uploaded_file.state.name)
                await asyncio.sleep(2)
                uploaded_file = await self.genai_client.aio.files.get(name=uploaded_file.name)

            logger.info("File '%s' is ACTIVE and ready.", filename)
            return types.Part.from_uri(file_uri=uploaded_file.uri, mime_type=uploaded_file.mime_type)

        except Exception as e:
            logger.exception("FileManager error during upload: %s", e)
            return None
