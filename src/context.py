from typing import List
from google.genai import types

from src.logger import setup_logger

logger = setup_logger(__name__)

class ContextManager:
    def __init__(self, system_prompt: str):
        self.system_prompt = system_prompt
        self.history: List[types.Content] = []

    def add_user_message(self, text: str):
        self.history.append(types.Content(role="user", parts=[types.Part.from_text(text=text)]))

    def add_model_message(self, text: str):
        self.history.append(types.Content(role="model", parts=[types.Part.from_text(text=text)]))

    def get_contents(self) -> List[types.Content]:
        return self.history