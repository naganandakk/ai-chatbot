import pytest

from core.chat_core.providers.pricing import anthropic_cost


def test_cost_counts_input_cache_output_and_searches():
    cost = anthropic_cost(
        "claude-opus-5",
        input_tokens=1_000_000,
        cache_write_tokens=1_000_000,
        cache_read_tokens=1_000_000,
        output_tokens=1_000_000,
        web_searches=100,
    )

    # $5 input + $6.25 cache write + $0.50 cache read + $25 output + $1 for 100 searches
    assert cost == pytest.approx(37.75)


def test_unknown_model_has_no_cost():
    assert anthropic_cost(
        "claude-unknown",
        input_tokens=10,
        cache_write_tokens=0,
        cache_read_tokens=0,
        output_tokens=10,
        web_searches=0,
    ) is None


def test_haiku_prompts_over_100k_tokens_use_long_prompt_rates():
    short = anthropic_cost(
        "claude-haiku-5-5",
        input_tokens=100_000,
        cache_write_tokens=0,
        cache_read_tokens=0,
        output_tokens=0,
        web_searches=0,
    )
    long = anthropic_cost(
        "claude-haiku-5-5",
        input_tokens=90_000,
        cache_write_tokens=0,
        cache_read_tokens=10_001,
        output_tokens=0,
        web_searches=0,
    )

    # 100,000 tokens at $0.10 per million, versus 100,001 tokens billed at the long-prompt rate
    assert short == pytest.approx(0.01)
    assert long == pytest.approx(90_000 * 0.5 / 1e6 + 10_001 * 0.05 / 1e6)
