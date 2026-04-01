import asyncio
from pathlib import Path
from typing import Optional, Union

from google import genai
from google.genai import types

from src.logger import get_logger

logger = get_logger("file_manager")


class FileManager:
    def __init__(self, genai_client: genai.Client):
        self.genai_client = genai_client
        self.downloads_dir = Path("./downloads")
        self.downloads_dir.mkdir(exist_ok=True)

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
                    logger.error("File to upload not found: %s", path_to_upload)
                    return None # Return None on failure
            else:
                path_to_upload = self.downloads_dir / filename
                path_to_upload.write_bytes(file_data)

            logger.info("Uploading file '%s'...", filename)
            uploaded_file = await self.genai_client.aio.files.upload(file=path_to_upload)

            # Wait for the file to be active
            while uploaded_file.state.name != "ACTIVE":
                if uploaded_file.state.name == "FAILED":
                    logger.error("File upload failed for '%s'. State: FAILED", filename)
                    return None # Return None on failure
                await asyncio.sleep(1)
                uploaded_file = await self.genai_client.aio.files.get(name=uploaded_file.name)
            
            logger.info("File '%s' is active.", filename)
            return types.Part.from_uri(file_uri=uploaded_file.uri, mime_type=uploaded_file.mime_type)

        except Exception as e:
            # In the new simplified model, we just log the error and return None.
            # The assistant will not receive specific feedback about this failure.
            logger.error("An unexpected error occurred during file upload for '%s': %s", filename, e, exc_info=True)
            return None
