import time

from google import genai
from google.genai import types

from llm.base import LLMProvider, LLMResponse


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str):
        self._client = genai.Client(api_key=api_key)

    def complete(self, model: str, prompt: str, web_search: bool = False) -> LLMResponse:
        start = time.monotonic()

        config = None
        if web_search:
            config = types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            )

        response = self._client.models.generate_content(
            model=model,
            contents=prompt,
            config=config,
        )
        latency_ms = int((time.monotonic() - start) * 1000)

        meta = getattr(response, "usage_metadata", None)
        return LLMResponse(
            content=response.text,
            tokens_in=getattr(meta, "prompt_token_count", None),
            tokens_out=getattr(meta, "candidates_token_count", None),
            latency_ms=latency_ms,
        )
