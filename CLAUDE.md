# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install / sync dependencies
poetry install

# Run a script
poetry run python scripts/<script>.py

# Lint
poetry run ruff check src/ scripts/

# Run all tests
poetry run pytest

# Run a single test file
poetry run pytest tests/test_earnings_event.py -v

# Interactive exploration
poetry run jupyter lab
```

## What this project does

Short-term earnings news trader for DAX/MDAX/SDAX companies. The pipeline has four stages:

1. **Calendar** — fetch upcoming earnings dates (Yahoo Finance, next 30 days, confirmed only) → `earnings_events` table
2. **T-1 prep** — day before each event: LLM with web search researches market expectations and writes a free-form trade thesis → `expectations_snapshots` table
3. **T0 release** — EQS news poller detects the actual announcement; ensemble of 4 LLMs evaluates it → `trade_decisions` table
4. **Decision log** — buy/skip recommendation stored for future analysis (no live trading in v1)

## Architecture

All source lives under `src/`. Scripts in `scripts/` are thin entry points that call into `src/`.

| Module | Responsibility |
|---|---|
| `config.py` | Env loading, paths, `ROLE_MODELS` dict mapping role → (provider, model) |
| `db/` | `get_engine`, `get_session`, `bootstrap`, `read_all`; all SQLAlchemy models in `db/models.py` |
| `universe/` | Load `data/tradeable_universe.csv` → upsert `companies` table |
| `eqs/` | `client.py` (EQS HTTP API, unchanged from original); `news_poller.py` (async poll loop); `calendar_client.py` (EQS calendar — not currently used) |
| `earnings/` | `yf_calendar.py` (Yahoo Finance ISIN→date fetch); `calendar_sync.py` (upsert `earnings_events`); `matcher.py` (link news items to events); `time_estimator.py` (estimate intraday release time from history) |
| `llm/` | Provider-agnostic interface. `base.py` defines `LLMProvider` ABC + `LLMResponse`. `registry.py` `call_llm(role, prompt, engine, ...)` routes by `ROLE_MODELS`, calls the right provider, and persists every call to `llm_runs` |
| `expectations/` | T-1 researcher: web-search LLM writes `narrative_md` + `trade_thesis_md` (free-form markdown) → `expectations_snapshots` |
| `reaction/` | T0 reaction analyst: web-search LLM looks up live price move since release |
| `ensemble/` | `pipeline.py` orchestrates interpreter_a + interpreter_b (content analysis, no web search) + reaction_analyst + decider → `EnsembleResult` dataclass |
| `pipeline/` | `daily_prep.py` (T-1 cron); `release_handler.py` (scans recent news, triggers ensemble on matches) |

## Data

- `data/news.db` — SQLite; tables: `companies`, `news_items`, `earnings_events`, `llm_runs`, `expectations_snapshots`, `trade_decisions`
- `data/tradeable_universe.csv` — 159 companies (DAX/MDAX/SDAX), columns: `company_name, ISIN, index, industry, description`

Read any table into pandas: `from db import read_all; dfs = read_all()`.

## Key design decisions

- **Expectations are unstructured** — `narrative_md` and `trade_thesis_md` are free-form markdown, not fixed numeric fields, because the relevant KPIs differ per company/situation.
- **No stock price fetching** — the reaction-analyst LLM uses web search to look up live prices at decision time; nothing is stored locally.
- **Every LLM call is logged** — `llm_runs` has the full prompt, response, token counts, and latency for every call across all roles. This is the audit trail for future trade review.
- **Upsert key for earnings events** — `(isin, fiscal_period)`; re-running the calendar sync is safe.
- **LLM roles** — `interpreter_a` (Claude), `interpreter_b` (OpenAI gpt-4o), `reaction_analyst` (Gemini, web search), `decider` (Claude), `expectations_researcher` (Gemini, web search). Change assignments in `src/config.py` `ROLE_MODELS`.
- **10 companies unreachable via ISIN** — yfinance rejects ISINs with alphanumeric segments (e.g. TUI `DE000TUAG000`, Porsche AG `DE000PAG9116`). Ticker-based fallback not yet implemented.

## Operational scripts

| Script | When to run |
|---|---|
| `scripts/sync_universe.py` | One-off or when `tradeable_universe.csv` changes |
| `scripts/sync_earnings_calendar.py` | Daily cron — refreshes next-30-day confirmed earnings dates |
| `scripts/run_news_poller.py` | Long-running daemon — polls EQS every 30s |
| `scripts/run_daily_prep.py` | Evening cron (T-1) — researches tomorrow's events |
| `scripts/run_release_handler.py` | Intraday cron — scans recent news for earnings matches, triggers ensemble |
