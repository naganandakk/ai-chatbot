---
name: add-provider
description: Scaffold a new AI model provider for ai-chatbot, including the provider class, registration in PROVIDERS, settings, and tests with a fake client or httpx MockTransport. Use when the user asks to add a model provider or API backend (for example Gemini, OpenAI, or another gateway).
---

# Add a model provider

Read these files first, because their current shape is the contract:
- `core/chat_core/providers/base.py` (the `ModelProvider` protocol, `TextDelta`, `Citation`, `ProviderError`)
- `core/chat_core/providers/__init__.py` (`PROVIDERS`, `create_provider`, `create_provider_by_name`)
- `core/chat_core/providers/anthropic_provider.py` (the simplest reference)
- `core/chat_core/providers/openrouter_provider.py` (the reference for citations and transports)
- `core/chat_core/settings.py` (how `AI_PROVIDER` and API keys are read)
- `core/chat_core/providers/pricing.py` (per-model pricing, if the provider has priced models)

Ask the user for the provider name and its SDK package only if they have not given them. Otherwise proceed.

## Rules

- Each provider uses its own SDK. Do not route a provider through another provider's SDK.
- Wrap all SDK exceptions in `ProviderError`. The service and CLI must never import SDK exception classes.
- `stream(model=, messages=, tools=)` yields `TextDelta` and `Citation` events only.
- If the SDK drops citation annotations from streamed deltas, follow the `openrouter_http.py` pattern: wrap the HTTP client and read raw SSE. Bind the sources list per reply with a context manager, and do not share it across threads.
- Use `max_tokens` from settings. For OpenRouter this is sent as `max_completion_tokens`. Keep the provider's own parameter name.

## Steps

1. Create `core/chat_core/providers/<name>_provider.py` with a class that implements the protocol. Accept `api_key=` and `max_tokens=` in the constructor, and accept an injectable `client=` or `transport=` so tests can run without the network.
2. Register it in `PROVIDERS` in `providers/__init__.py` under its lowercase name. Export it from the package `__all__` if the other providers are exported.
3. If the provider needs a new API-key variable, check `api_key_from_env` in `settings.py` and add the mapping there. Update `.env.example` with the variable name and no value.
4. Add pricing entries in `pricing.py` only if the provider's models have known prices. If prices are unknown, say so and leave them out.
5. Add the dependency with `uv add <package>` and let `uv` update `pyproject.toml` and `uv.lock`.
6. Write tests in `tests/test_<name>_provider.py`:
   - A fake client or `httpx.MockTransport` for the streaming path
   - A test that an SDK error becomes `ProviderError`
   - A test that the provider is returned by `create_provider` when `AI_PROVIDER` names it
   Follow the injection style used by the existing tests. Do not add a live-API test.
7. Run `uv run ruff check .` and `uv run pytest`.

## Report

List the files created and changed, the environment variable added, and the test results. State if pricing was skipped and why. Do not commit unless the user asks.
