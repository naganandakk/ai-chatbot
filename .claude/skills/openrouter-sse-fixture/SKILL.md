---
name: openrouter-sse-fixture
description: Create or update raw OpenRouter SSE stream fixtures, including url_citation annotations, for testing the citation path in core/chat_core/providers/openrouter_http.py. Use when changing the OpenRouter citation parsing, adding a test for a new streamed chunk shape, or reproducing a sources bug from a captured stream.
---

# OpenRouter SSE fixtures

The OpenRouter SDK drops `url_citation` annotations from streamed deltas, so `providers/openrouter_http.py` wraps the httpx client and reads the raw SSE lines itself. Tests for that path must use raw SSE bytes, not SDK objects, because the bug lives in what the SDK discards.

Read these first:
- `core/chat_core/providers/openrouter_http.py` (`CitationStream._record`, `CitationHttpClient.collecting`)
- `core/chat_core/providers/openrouter_provider.py` (how the per-reply sources list is bound and emitted)
- the existing OpenRouter tests. Find them with `grep -rln "MockTransport\|openrouter" tests/`

## Format

Each event is one `data:` line followed by a blank line. The stream ends with `data: [DONE]`. A chunk that carries an error must produce a `ProviderError` on the provider side.

Example shape of a text chunk with a citation:

```
data: {"id":"gen-1","choices":[{"index":0,"delta":{"content":"Paris"},"finish_reason":null}]}

data: {"id":"gen-1","choices":[{"index":0,"delta":{"content":"","annotations":[{"type":"url_citation","url_citation":{"url":"https://example.com/a","title":"Example A"}}]},"finish_reason":null}]}

data: [DONE]

```

Check the field names against the current `_record` implementation and against any real captured stream. Do not trust this example over the code.

## Steps

1. Decide the case to cover: plain text, one citation, several citations, duplicate URLs, a chunk with an `error`, or a malformed line.
2. Write the fixture as a Python bytes or string constant inside the test file, unless several tests share it. Only then create a file under `tests/fixtures/`.
3. Feed it through `httpx.MockTransport` into `OpenRouterProvider(transport=...)`, so the real SDK and wrapper run. Do not mock the wrapper itself.
4. Assert on the yielded `TextDelta` and `Citation` events, and on the order of citations relative to the text.
5. If the fixture came from a real request, strip API keys, account IDs, and any personal data before saving it. Say in the report that it was captured and scrubbed.
6. Run `uv run pytest` and `uv run ruff check .`.

## Report

Give the fixture file or constant, the cases covered, and the test results. If the fixture was hand-written and not captured from a real stream, say so, since the real stream may differ.
