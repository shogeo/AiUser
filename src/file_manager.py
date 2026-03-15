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
        """Извлекает имя файла из данных."""
        if isinstance(file_data, (str, Path)):
            return Path(file_data).name
        else:  # bytes
            return f"temp_bytes_{hash(file_data)}.bin"

    async def upload_and_get_part(self, file_data: Union[str, Path, bytes]) -> Optional[types.Part]:
        """
        Загружает файл в Gemini, ожидает его активации и возвращает Part с file_uri.
        """
        path_to_upload = None
        filename = self.get_filename(file_data)
        
        try:
            if isinstance(file_data, (str, Path)):
                path = Path(file_data)
                if not path.exists():
                    logger.error("File not found for upload: %s", path)
                    return None
                path_to_upload = path
            elif isinstance(file_data, bytes):
                temp_path = self.downloads_dir / filename
                temp_path.write_bytes(file_data)
                path_to_upload = temp_path
                logger.debug("Byte data saved to temporary file: %s", temp_path)
            else:
                logger.error("Unsupported file data type for upload: %s", type(file_data))
                return None

            logger.info("Uploading '%s' to Gemini File API...", filename)
            uploaded_file = await self.genai_client.files.upload(file=path_to_upload)
            logger.info("File '%s' uploaded. Name: %s. Waiting for it to become ACTIVE...", filename, uploaded_file.name)

            # --- ЦИКЛ ОЖИДАНИЯ ---
            while uploaded_file.state.name != "ACTIVE":
                if uploaded_file.state.name == "FAILED":
                    logger.error("File '%s' failed to process.", uploaded_file.name)
                    return None
                await asyncio.sleep(1) # Пауза в 1 секунду
                logger.debug("Checking file state for %s...", uploaded_file.name)
                uploaded_file = await self.genai_client.files.get(name=uploaded_file.name)

            logger.info("File '%s' is now ACTIVE. URI: %s", filename, uploaded_file.uri)
            
            return types.Part.from_uri(file_uri=uploaded_file.uri, mime_type=uploaded_file.mime_type)

        except Exception as e:
            logger.exception("Failed to upload or process file '%s': %s", filename, e)
            return None