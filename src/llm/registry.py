import logging
import uuid
from datetime import datetime, timezone

from config import CLAUDE_API_KEY, GEMINI_API_KEY, OPENAI_API_KEY, ROLE_MODELS
from db import get_session
from db.models import LLMRun
from llm.claude import ClaudeProvider
from llm.gemini import GeminiProvider
from llm.openai import OpenAIProvider

logger = logging.getLogger(__name__)

_FACTORIES = {
    "claude": lambda: ClaudeProvider(CLAUDE_API_KEY),
    "openai": lambda: OpenAIProvider(OPENAI_API_KEY),
    "gemini": lambda: GeminiProvider(GEMINI_API_KEY),
}


def call_llm(
    role: str,
    prompt: str,
    engine,
    earnings_event_id: str | None = None,
    web_search: bool = False,
) -> tuple[str, str]:
    """
    Call the LLM assigned to `role`, persist the run to llm_runs.
    Returns (response_text, llm_run_id).
    """
    provider_name, model = ROLE_MODELS[role]
    provider = _FACTORIES[provider_name]()

    logger.info(
        "LLM call: role=%s provider=%s model=%s web_search=%s", role, provider_name, model, web_search
    )
    response = provider.complete(model, prompt, web_search=web_search)
    logger.info(
        "LLM done: role=%s tokens_in=%s tokens_out=%s latency=%dms",
        role, response.tokens_in, response.tokens_out, response.latency_ms,
    )

    run_id = str(uuid.uuid4())
    session = get_session(engine)
    try:
        session.add(
            LLMRun(
                id=run_id,
                earnings_event_id=earnings_event_id,
                role=role,
                provider=provider_name,
                model=model,
                prompt=prompt,
                response=response.content,
                tokens_in=response.tokens_in,
                tokens_out=response.tokens_out,
                latency_ms=response.latency_ms,
                created_at=datetime.now(timezone.utc),
            )
        )
        session.commit()
    finally:
        session.close()

    return response.content, run_id
