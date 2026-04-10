import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "news.db"
UNIVERSE_CSV = DATA_DIR / "tradeable_universe.csv"

CLAUDE_API_KEY: str = os.environ["CLAUDE_API_KEY"]
OPENAI_API_KEY: str = os.environ["OPENAI_API_KEY"]
GEMINI_API_KEY: str = os.environ["GEMINI_API_KEY"]

# LLM role assignments: role → (provider, model)
# Roles that use web search at runtime: expectations_researcher, reaction_analyst
ROLE_MODELS: dict[str, tuple[str, str]] = {
    "interpreter_a": ("claude", "claude-sonnet-4-5"),
    "interpreter_b": ("openai", "gpt-4o"),
    "reaction_analyst": ("gemini", "gemini-3-flash-preview"),
    "decider": ("claude", "claude-sonnet-4-5"),
    "expectations_researcher": ("gemini", "gemini-3-flash-preview"),
}
