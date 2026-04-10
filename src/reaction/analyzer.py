from db.models import Company, EarningsEvent
from llm.registry import call_llm

_PROMPT = """\
You are a financial analyst. An earnings announcement was just released and you need to \
assess the stock market reaction in real time.

Company: {company_name} ({isin}, {index_name} index)
Announcement released at: {actual_release_at}

Please search for up-to-date stock price information and provide:
1. The stock price just before the announcement (approximate)
2. The current stock price
3. The percentage change since the announcement
4. Any notable intraday patterns (e.g. initial spike then reversal, continued drift upward)
5. Your assessment: does the move appear consistent with the announcement content, and does \
the news appear to NOT yet be fully priced in — i.e. is there remaining upside potential \
of at least 5%?

Be specific about prices, times, and sources.
"""


def analyze(event: EarningsEvent, company: Company, engine) -> tuple[str, str]:
    """
    Run the reaction-analyst LLM (with web search) for a just-released earnings event.
    Returns (response_text, llm_run_id).
    """
    prompt = _PROMPT.format(
        company_name=company.name,
        isin=company.isin,
        index_name=company.index_name,
        actual_release_at=str(event.actual_release_at),
    )
    return call_llm(
        role="reaction_analyst",
        prompt=prompt,
        engine=engine,
        earnings_event_id=event.id,
        web_search=True,
    )
