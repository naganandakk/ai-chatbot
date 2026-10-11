from dataclasses import dataclass

# Anthropic does not return a dollar cost, so it is worked out from token counts. Prices are
# from Anthropic's pricing page and must be updated by hand when they change. A model that is
# not listed reports its tokens with no cost.


@dataclass(frozen=True)
class Rates:
    """USD per million tokens."""

    input: float
    cache_write: float
    cache_read: float
    output: float


# Keys are the API model IDs. Cache writes are all priced at the 5-minute rate, so 1-hour
# cache writes are billed low.
ANTHROPIC_RATES: dict[str, Rates] = {
    "claude-fable-5-1": Rates(input=10, cache_write=12.5, cache_read=0.25, output=50),
    "claude-fable-5": Rates(input=10, cache_write=12.5, cache_read=1, output=50),
    "claude-opus-5-5": Rates(input=4, cache_write=5, cache_read=0.2, output=20),
    "claude-opus-5": Rates(input=5, cache_write=6.25, cache_read=0.5, output=25),
    "claude-sonnet-5-5": Rates(input=2, cache_write=2.5, cache_read=0.1, output=10),
    "claude-sonnet-5": Rates(input=2, cache_write=2.5, cache_read=0.2, output=10),
    "claude-haiku-5-5": Rates(input=0.1, cache_write=0.125, cache_read=0.01, output=0.5),
}

# Haiku 5.5 bills prompts over this many tokens at a higher rate. The prompt counts input,
# cache writes, and cache reads together.
LONG_PROMPT_TOKENS = 100_000
LONG_PROMPT_RATES: dict[str, Rates] = {
    "claude-haiku-5-5": Rates(input=0.5, cache_write=0.625, cache_read=0.05, output=2.5),
}

# $10 per 1,000 web searches
WEB_SEARCH_USD = 0.01


def anthropic_cost(
    model: str,
    *,
    input_tokens: int,
    cache_write_tokens: int,
    cache_read_tokens: int,
    output_tokens: int,
    web_searches: int,
) -> float | None:
    rates = ANTHROPIC_RATES.get(model)
    if rates is None:
        return None

    prompt_tokens = input_tokens + cache_write_tokens + cache_read_tokens
    if model in LONG_PROMPT_RATES and prompt_tokens > LONG_PROMPT_TOKENS:
        rates = LONG_PROMPT_RATES[model]

    token_cost = (
        input_tokens * rates.input
        + cache_write_tokens * rates.cache_write
        + cache_read_tokens * rates.cache_read
        + output_tokens * rates.output
    ) / 1_000_000

    return token_cost + web_searches * WEB_SEARCH_USD
