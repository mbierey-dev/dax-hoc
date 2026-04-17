# Decision Logic — Agentic Pipeline

Short-term earnings trade system for DAX/MDAX/SDAX and EURO STOXX 50 companies. Six LLM roles across four pipeline stages.

---

## Pipeline Overview

```
T-1 (evening before)
  └── expectations_researcher   → ExpectationsSnapshot (narrative + trade thesis)

T0 (announcement day)
  └── announcement_fetcher      → structured announcement summary
        ├── interpreter_a       ┐  (run in parallel)
        └── interpreter_b       ┘
              └── decider       → TradeDecision (BUY / SKIP)

T+1 (next day)
  └── feedback_analyst          → FeedbackReport (post-mortem)
```

---

## Roles

### 1. `expectations_researcher`
**When:** Evening before the earnings release (T-1 cron)  
**Model:** `gpt-5.4` (OpenAI) — reasoning_effort=high, web_search always on  
**Purpose:** Research what analysts and the market expect from this release. Produce a free-form narrative and a concrete, company-specific trade thesis.

**Prompt inputs:**
- Company name, ISIN, index, industry
- Fiscal period and event type (full-year / quarterly)
- Expected release date

**Prompt asks the model to:**
1. Research analyst consensus and key KPIs to watch for *this* company (not generic revenue/EPS)
2. Identify what is already priced in
3. Define up to 3 concrete, company-specific buy conditions

**Output (3 sections parsed into DB):**
- `narrative_md` — Market Narrative & Key Watchpoints
- `trade_thesis_md` — Trade Thesis (concrete buy conditions + deal-breakers)
- `sources_json` — URLs consulted

**Side effect:** Also fetches pre-announcement price returns (1d / 3d / 7d, vs MSCI World benchmark) and stores them on the `ExpectationsSnapshot`.

---

### 2. `announcement_fetcher`
**When:** At T0 — first step of the ensemble run  
**Model:** `gpt-5.4` (OpenAI) — reasoning_effort=high, web_search always on  
**Purpose:** Retrieve the actual earnings press release and produce a structured summary.

**Prompt inputs:**
- Company name, ISIN, index
- Fiscal period and event type

**Prompt asks the model to:**
1. Search for the official earnings release
2. Lead with an ISO 8601 release timestamp (`RELEASE_DATETIME: <ts>`)
3. Summarize under three headings: Reported KPIs / Guidance / Key Qualitative Highlights

**Output (parsed):**
- `release_at` — extracted timestamp; written back to `earnings_events.actual_release_at`
- `summary` — the three-section text passed to both interpreters and the decider

---

### 3. `interpreter_a`
**When:** T0 — runs in parallel with interpreter_b  
**Model:** `claude-opus-4-7` (Claude) — adaptive thinking enabled, web_search always on (all Opus models), max_tokens=16,000  
**Purpose:** Independently evaluate the announcement against pre-release expectations and estimate the likely short-term market reaction.

**Prompt inputs:**
- Company name, ISIN, index, industry, fiscal period
- `narrative_md` from the expectations snapshot (what the market expected)
- Announcement summary from `announcement_fetcher`

**Prompt asks the model to cover:**
- Beat / in-line / miss on key KPIs
- Guidance vs prior guidance and vs street consensus
- Key positive and negative surprises
- Overall reaction estimate: strong positive / positive / neutral / negative / strong negative + 1–2 sentence rationale

**Output:** Free-form analysis text, passed directly to the decider.

---

### 4. `interpreter_b`
**When:** T0 — runs in parallel with interpreter_a  
**Model:** `gpt-5.4` (OpenAI) — reasoning_effort=high, web_search always on  
**Purpose:** Same task as interpreter_a but with a different model to reduce single-model bias. The decider sees both.

**Prompt:** Identical structure to interpreter_a.

**Output:** Free-form analysis text, passed directly to the decider.

---

### 5. `decider`
**When:** T0 — after both interpreters have finished  
**Model:** `claude-opus-4-7` (Claude) — adaptive thinking, web_search always on (Opus), max_tokens=16,000  
**Purpose:** Synthesize all inputs and issue a final BUY / SKIP decision.

**Prompt inputs:**
- Company name, ISIN, index, fiscal period, actual release timestamp
- Pre-announcement price momentum (1d / 3d / 7d abnormal returns vs MSCI World) — if available
- `trade_thesis_md` — the buy conditions written at T-1
- interpreter_a full response
- interpreter_b full response
- Announcement summary

**Buy bar (explicit in the prompt):** BUY only if the stock is highly likely to rise at least an additional 5% as a *direct result* of this announcement AND the move is not yet fully priced in.

**Output (structured, parsed by regex):**
```
DECISION: BUY or SKIP
CONFIDENCE: 0.00–1.00
EXPECTED_UPSIDE_PCT: e.g. 7.5
REASONING: 2–4 sentence summary
MISSING_INFORMATION: (optional) data that was absent and would have changed the decision
```

Stored as a `TradeDecision` row.

---

### 6. `feedback_analyst`
**When:** T+1 (next trading day after the announcement)  
**Model:** `claude-sonnet-4-6` (Claude) — web_search enabled, max_tokens=4,096  
**Purpose:** Post-mortem. Compare the system's decision against the actual stock return and extract generalizable learnings.

**Prompt inputs (full audit trail):**
- Company name, ISIN, index, industry, fiscal period, event date
- `narrative_md` and `trade_thesis_md` (T-1 expectations)
- Announcement summary (T0)
- interpreter_a and interpreter_b full responses
- System decision, confidence, expected upside, reasoning, and any flagged missing information
- Actual T0 stock return (close-to-close)

**Correctness threshold (explicit in the prompt):** BUY is correct if return > +3%; SKIP is correct if return < +3%.

**Output (3 sections, parsed):**
- `market_narrative_md` — Decision Assessment: CORRECT / INCORRECT / PARTIAL + explanation including what the market narrative actually was
- `key_learnings_md` — Signals the system over/underweighted; concrete KPIs or patterns that mattered
- `improvement_suggestions_md` — 3–5 actionable, general improvements to the research or decision process

Stored as a `FeedbackReport` row.

---

## Model Capabilities Summary

| Role | Provider | Model | Thinking | Web Search | Max Tokens |
|---|---|---|---|---|---|
| expectations_researcher | OpenAI | gpt-5.4 | reasoning_effort=high | always on | — |
| announcement_fetcher | OpenAI | gpt-5.4 | reasoning_effort=high | always on | — |
| interpreter_a | Claude | claude-opus-4-7 | adaptive (always) | always on | 16,000 |
| interpreter_b | OpenAI | gpt-5.4 | reasoning_effort=high | always on | — |
| decider | Claude | claude-opus-4-7thin | adaptive (always) | always on | 16,000 |
| feedback_analyst | Claude | claude-sonnet-4-6 | — | on (explicit flag) | 4,096 |

> Model assignments live in `src/config.py` → `ROLE_MODELS`. Roles with web search are noted in the comment above that dict.
