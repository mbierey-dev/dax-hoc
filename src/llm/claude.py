import time

import anthropic

from llm.base import LLMProvider, LLMResponse


class ClaudeProvider(LLMProvider):
    def __init__(self, api_key: str):
        self._client = anthropic.Anthropic(api_key=api_key)

    def complete(self, model: str, prompt: str, web_search: bool = False) -> LLMResponse:
        start = time.monotonic()
        kwargs: dict = {
            "model": model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        if web_search:
            kwargs["tools"] = [
                {"type": "web_search_20250305", "name": "web_search", "max_uses": 5}
            ]

        response = self._client.messages.create(**kwargs)
        latency_ms = int((time.monotonic() - start) * 1000)

        content = "".join(
            block.text for block in response.content if hasattr(block, "text")
        )
        return LLMResponse(
            content=content,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
            latency_ms=latency_ms,
        )
