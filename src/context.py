from typing import List, Optional
from google.genai import types

class ContextManager:
    def __init__(self, system_prompt: str):
        self.system_prompt = system_prompt
        self.history: List[types.Content] = []

    def get_system_prompt(self) -> str:
        return self.system_prompt

    def add_user_message(self, text: str, file_part: Optional[types.Part] = None):
        parts = [types.Part.from_text(text=text)]
        if file_part:
            parts.append(file_part)
        self.history.append(types.Content(role="user", parts=parts))

    def add_model_message(self, text: str):
        self.history.append(types.Content(role="model", parts=[types.Part.from_text(text=text)]))

    def get_contents(self) -> List[types.Content]:
        return self.history
