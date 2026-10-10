# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Python (managed with `uv`, run from repo root):

```bash
uv sync --all-groups                 # install deps incl. dev (pytest, ruff)
uv run pytest                        # full test suite (17 tests, ~1s, no network)
uv run pytest tests/test_service.py::test_stream_reply_saves_user_and_assistant_messages  # single test
uv run ruff check .                  # lint (line-length 100, py311)
uv run flask --app backend.app.wsgi:app run --debug --no-reload --port 5000   # API
uv run gunicorn --workers 1 --timeout 120 --bind 127.0.0.1:5000 backend.app.wsgi:app   # production-style server
uv run python -m cli.main            # terminal client
```

Frontend (from `frontend/`):

```bash
npm install
npm run dev                          # Vite dev server on :5173, proxies /api -> 127.0.0.1:5000
npm run build                        # runs tsc -b then vite build; passes
```

Always use `--no-reload` with Flask: DuckDB takes a write lock on the database file and the reloader's second process will fail to open it.

## Architecture

The project is three layers sharing one core: a Flask API (`backend/`), a terminal client (`cli/`), and a React SPA (`frontend/`). Both entry points call the same `core/chat_core` service.

**Request flow for a chat message.** Browser `streamMessage()` in `frontend/src/api.ts` POSTs to `/api/sessions/<id>/messages`. `backend/app/__init__.py:create_app` builds a generator that iterates `ChatService.stream_reply()` and frames each chunk as Server-Sent Events (`event: delta`, `event: done`, `event: error`). The frontend parses these frames by splitting on `\n\n`, so any change to the SSE format must be made in both files.

**`ChatService.stream_reply`** (`core/chat_core/service.py`) is the core of the app:
1. Saves the user message to the store *before* calling the model. If the model call then fails, the user message remains persisted with no assistant reply.
2. Loads the full session history and sends it to the model with `stream=True`. Anthropic requests go through the Anthropic SDK with `max_tokens=2048`. OpenRouter requests go through the OpenRouter SDK (`openrouter` package) with `max_completion_tokens=2048`.
3. Yields text deltas to the caller. Any `citations_delta` events are collected as `{title, url}` sources, then the full assistant text and sources are saved as one message.
4. If `tools_enabled` is set (from `TOOLS_ENABLED`, e.g. `web_search`), it is passed to the API as server tools; citations from those tools are what populate `sources`.

**Provider switching.** `Settings.from_env()` (`core/chat_core/settings.py`) reads `AI_PROVIDER` (`anthropic` or `openrouter`) and selects the matching API key and default model. `ChatService.stream_reply` picks a streaming helper by provider: `_anthropic_deltas` uses the Anthropic SDK, and `_openrouter_deltas` uses the OpenRouter SDK (`from openrouter import OpenRouter`, one cached client per `ChatService`). Both yield plain text deltas, so the save logic is shared. Keep the two SDKs separate: do not route OpenRouter through the Anthropic SDK. OpenRouter web search is enabled by `TOOLS_ENABLED=web_search`, which maps to the `web` plugin. The OpenRouter SDK's models drop `url_citation` annotations from streamed deltas, so `core/chat_core/openrouter_http.py` wraps the cached httpx client and reads the raw SSE lines. `ChatService` binds each reply's sources list to the calling thread with `CitationHttpClient.collecting(sources)`, and the tap appends `{title, url}` citations into it. Binding is per thread, so concurrent replies on threaded workers each keep their own citations. Do not share the sources list across threads or move the `collecting` block outside the request's send/stream. The service accepts `openrouter_transport` (an `httpx` transport) so tests can run the real SDK against `httpx.MockTransport`.

**Storage has two implementations behind one duck-typed interface.** `SessionStore` (`store.py`) is in-memory and is the default for `create_app()` and for the CLI. `DuckDBSessionStore` (`duckdb_store.py`) is used by `backend/app/wsgi.py` and persists to `CHAT_DATABASE_PATH` (default `data/chat.duckdb`). Any new store method must be implemented in both files. Both raise `KeyError` for unknown session IDs, and the Flask routes map that to 404. The DuckDB store also derives the session title from the first user message (first 48 characters, newlines flattened).

**Configuration loading.** `.env` is loaded from the repo root by `settings.py` and again by `wsgi.py`. `Settings.from_env()` is called lazily inside `ChatService`, so missing config raises at first message, not at import. The CLI catches `RuntimeError` as a configuration error.

**Testing approach.** Tests inject fakes rather than hitting the network: `FakeClaudeClient` (duck-typed `.messages.create`) is passed as `ChatService(client=...)`, and `FakeChatService` is passed to `create_app(chat_service=...)`. Keep new tests in this style; there is no live-API test.

**Frontend state.** A single React context (`frontend/src/Context.tsx`) holds the active session, session list, `isGenerating`, sidebar state, and a toast-style error stack. Components read it via `useContext(Context)`. The Vite dev server is the only proxy to Flask, so frontend code uses relative `/api` paths.

## Known state

- `npm run build` passes: `tsc -b` reports no type errors and the Vite bundle builds.
- `uv run ruff check .` passes. The CLI catches `anthropic.APIError`, `openrouter.errors.OpenRouterError`, and `ProviderStreamError` (raised when an OpenRouter stream chunk carries an `error`) for request failures, so other exceptions propagate instead of being printed.
- `uv run pytest` passes (17 tests).
- Production runs Gunicorn with `--workers 1 --timeout 120` (see README "Production deployment"). Workers must stay at 1: DuckDB takes a write lock, and each worker opens the file at import. The default `sync` worker serves one request at a time, so a streaming reply blocks other requests. Threads can go above 1 safely now: `DuckDBSessionStore` serializes every public method with a lock around its shared connection. Raising threads still needs `--worker-class gthread`, since the `sync` worker ignores `--threads`.
- The default Gunicorn timeout (30s) is too short for slow model replies, which is why the command sets `--timeout 120`.
