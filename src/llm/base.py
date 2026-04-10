from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    content: str
    tokens_in: int | None
    tokens_out: int | None
    latency_ms: int


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, model: str, prompt: str, web_search: bool = False) -> LLMResponse:
        ...
