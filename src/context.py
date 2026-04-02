import json
from typing import List, Optional

from google.genai import types

from src.config import CONTEXT_FILE_PATH


class ContextManager:
    def __init__(self, system_prompt: str):
        self.system_prompt = system_prompt
        self.history: List[types.Content] = []
        self._load_from_file()
        self._save_to_file()

    def _load_from_file(self):
        if CONTEXT_FILE_PATH.exists():
            with open(CONTEXT_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data:
                    self.history.append(types.Content(role=item["role"], parts=[types.Part.from_text(text=item["content"])]))

    def _save_to_file(self):
        data = []
        for content in self.history:
            data.append({"role": content.role, "content": content.parts[0].text})
        with open(CONTEXT_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_system_prompt(self) -> str:
        return self.system_prompt

    def add_user_message(self, text: str, file_part: Optional[types.Part] = None):
        parts = [types.Part.from_text(text=text)]
        if file_part:
            parts.append(file_part)
        self.history.append(types.Content(role="user", parts=parts))
        self._save_to_file()

    def add_model_message(self, text: str):
        self.history.append(types.Content(role="model", parts=[types.Part.from_text(text=text)]))
        self._save_to_file()

    def get_contents(self) -> List[types.Content]:
        return self.history
