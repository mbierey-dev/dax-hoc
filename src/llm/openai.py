import time

from openai import OpenAI

from llm.base import LLMProvider, LLMResponse

# For roles that need web search, swap to the search-enabled model
_SEARCH_MODEL = "gpt-4o-search-preview"


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str):
        self._client = OpenAI(api_key=api_key)

    def complete(self, model: str, prompt: str, web_search: bool = False) -> LLMResponse:
        start = time.monotonic()
        is_gpt54 = model == "gpt-5.4"
        actual_model = model if is_gpt54 else (_SEARCH_MODEL if web_search else model)
        kwargs: dict = {
            "model": actual_model,
            "messages": [{"role": "user", "content": prompt}],
        }
        if is_gpt54:
            kwargs["reasoning_effort"] = "high"
            kwargs["tools"] = [{"type": "web_search"}]
        response = self._client.chat.completions.create(**kwargs)
        latency_ms = int((time.monotonic() - start) * 1000)
        usage = response.usage
        return LLMResponse(
            content=response.choices[0].message.content or "",
            tokens_in=usage.prompt_tokens if usage else None,
            tokens_out=usage.completion_tokens if usage else None,
            latency_ms=latency_ms,
        )
