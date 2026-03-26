import asyncio
from pathlib import Path
from typing import Optional, Union

from google import genai
from google.genai import types


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
                    return None
            else:
                path_to_upload = self.downloads_dir / filename
                path_to_upload.write_bytes(file_data)

            uploaded_file = await self.genai_client.aio.files.upload(file=path_to_upload)

            while uploaded_file.state.name != "ACTIVE":
                if uploaded_file.state.name == "FAILED":
                    return None
                await asyncio.sleep(2)
                uploaded_file = await self.genai_client.aio.files.get(name=uploaded_file.name)

            return types.Part.from_uri(file_uri=uploaded_file.uri, mime_type=uploaded_file.mime_type)

        except Exception:
            return None
