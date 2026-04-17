import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "news.db"
UNIVERSE_CSV = DATA_DIR / "tradeable_universe.csv"

BENCHMARK_TICKER = "XDWD.DE"  # Xtrackers MSCI World UCITS ETF, EUR (Xetra)

CLAUDE_API_KEY: str = os.environ["CLAUDE_API_KEY"]
OPENAI_API_KEY: str = os.environ["OPENAI_API_KEY"]
GEMINI_API_KEY: str = os.environ["GEMINI_API_KEY"]

# LLM role assignments: role → (provider, model)
# Roles that use web search at runtime: expectations_researcher, announcement_fetcher, feedback_analyst
ROLE_MODELS: dict[str, tuple[str, str]] = {
    "expectations_researcher": ("openai", "gpt-5.4"),
    "announcement_fetcher": ("openai", "gpt-5.4"),
    "interpreter_a": ("claude", "claude-opus-4-7"),
    "interpreter_b": ("openai", "gpt-5.4"),
    "decider": ("claude", "claude-opus-4-7"),
    "feedback_analyst": ("claude", "claude-sonnet-4-6"),
}
