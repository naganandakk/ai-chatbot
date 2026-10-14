# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Python (managed with `uv`, run from repo root):

```bash
uv sync --all-groups                 # install deps incl. dev (pytest, ruff)
uv run pytest                        # full test suite (~1s, no network; Postgres contract tests skipped)
TEST_DATABASE_URL=postgresql:///chat_store_test uv run pytest   # also run Postgres store contract tests
uv run pytest tests/test_service.py::test_stream_reply_saves_user_and_assistant_messages  # single test
uv run ruff check .                  # lint (line-length 100, py311)
uv run flask --app backend.app.wsgi:app run --debug --no-reload --port 5000   # API
uv run gunicorn backend.app.wsgi:app   # production-style server; settings in gunicorn.conf.py (HTTPS when APP_ENV is local, the default)
uv run python -m cli.main            # terminal client
```

Postgres for the Postgres store and its contract tests. Locally, use any server that accepts connections (e.g. Homebrew `postgresql@17`, or Docker `postgres:17`). Create a disposable database and point `TEST_DATABASE_URL` at it; the tests `TRUNCATE` its tables before each check, so never reuse a database with data you keep:

```bash
createdb chat_store_test             # or: psql -c 'CREATE DATABASE chat_store_test'
TEST_DATABASE_URL=postgresql:///chat_store_test uv run pytest tests/test_store_contract.py
```

To run the app against Postgres locally, set `CHAT_STORE=postgres` and `DATABASE_URL=postgresql:///chat_dev` in `.env` (create that database first). Tables are created on first start.

Frontend (from `frontend/`):

```bash
npm install
npm run dev                          # Vite dev server on :5173, proxies /api -> 127.0.0.1:5000
npm run dev:lan                      # same, over HTTPS on the LAN for phone voice prompts; needs mkcert certs in frontend/certs (see README)
npm run build                        # runs tsc -b then vite build; passes
```

Always use `--no-reload` with Flask when `CHAT_STORE=duckdb`: DuckDB takes a write lock on the database file and the reloader's second process will fail to open it. The Postgres store has no such lock.

## Architecture

The project is three layers sharing one core: a Flask API (`backend/`), a terminal client (`cli/`), and a React SPA (`frontend/`). Both entry points call the same `core/chat_core` service.

**Request flow for a chat message.** Browser `streamMessage()` in `frontend/src/api.ts` POSTs to `/api/sessions/<id>/messages`. `backend/app/__init__.py:create_app` builds a generator that iterates `ChatService.stream_reply()` and frames each chunk as Server-Sent Events (`event: delta`, `event: done`, `event: error`). Every `/api` route except `/api/health` and the `/api/auth/*` routes needs a signed-in user: `backend/app/auth.py:install_auth` checks the `access_token` cookie (a 15-minute JWT) and sets `g.user_id`, which routes pass to the store. A 401 means the frontend should call `/api/auth/refresh` once and retry. The frontend parses these frames by splitting on `\n\n`, so any change to the SSE format must be made in both files. Messages with files are sent as `multipart/form-data` (`message`, `model`, repeated `files`); text-only messages stay JSON. `MAX_CONTENT_LENGTH` is set from the attachment limits, so an oversized upload gets a JSON 413 before it is read. Attachment validation lives in `core/chat_core/attachments.py` and runs before anything is saved.

**`ChatService.stream_reply`** (`core/chat_core/service.py`) is the core of the app:
1. Resolves the provider first. In the web app that is the caller's saved API key, decrypted by `KeyVault` and cached by `ProviderPool`; a missing key raises `ApiKeyRequired` (a `ValueError`) before anything is saved, and the SSE error event carries `code: "api_key_required"`. Then it saves the user message to the store *before* calling the model. If the model call then fails, the user message remains persisted with no assistant reply.
2. Loads the full session history and sends it to the model with `stream=True`. Anthropic requests go through the Anthropic SDK with `max_tokens` set from `MAX_TOKENS` (default 8192). OpenRouter requests go through the OpenRouter SDK (`openrouter` package) with `max_completion_tokens` set from the same value.
3. Yields text deltas to the caller. Any `citations_delta` events are collected as `{title, url}` sources, then the full assistant text and sources are saved as one message.
4. `tools` is the list of tool ids the user switched on for this message (`GET /api/tools` lists them from `core/chat_core/tools.py`). Every tool is off by default, and unknown ids are refused before anything is saved. The ids are passed to the API as server tools; citations from those tools are what populate `sources`.

**Providers.** `ModelProvider` (`core/chat_core/providers/base.py`) is a protocol: `stream(model=, messages=, tools=)` yields `TextDelta` and `Citation` events, and failures are raised as `ProviderError`. Implementations live beside it: `AnthropicProvider` (Anthropic SDK; maps tool ids to server tools) and `OpenRouterProvider` (OpenRouter SDK; `web_search` maps to the `web` plugin). Each provider wraps its own SDK errors, so the service and CLI never import SDK exceptions. `create_provider(settings)` in `providers/__init__.py` picks the class from `PROVIDERS` by `AI_PROVIDER`; add a new provider by writing a class and registering it there. Keep the SDKs separate: do not route OpenRouter through the Anthropic SDK. The OpenRouter SDK's models drop `url_citation` annotations from streamed deltas, so `providers/openrouter_http.py` wraps the cached httpx client and reads the raw SSE lines. `OpenRouterProvider.stream` binds its per-reply sources list to the calling thread with `CitationHttpClient.collecting(sources)`, and emits the collected citations once the stream ends. Binding is per thread, so concurrent replies on threaded workers each keep their own citations. Do not share the sources list across threads or move the `collecting` block outside the request's send/stream. `OpenRouterProvider(transport=...)` takes an `httpx` transport so tests can run the real SDK against `httpx.MockTransport`.

**Storage is an ABC.** `SessionStore` (`store.py`) declares the contract: create, get, list (summaries, newest first), add_message, clear, delete, update, and close. Every method takes `user_id` first, and another user's sessions and attachments behave exactly like unknown IDs (`KeyError`). `AccountStore` (`accounts.py`) covers users, refresh tokens (stored as hashes) and per-user provider API keys (stored encrypted by `KeyVault` in `key_vault.py`, bound to user and provider as AES-GCM associated data). `DuckDBSessionStore`, `PostgresSessionStore` and `InMemorySessionStore` implement both ABCs. Key saves and deletes are written to `audit_events` (user, provider, action, time; never the key). `InMemorySessionStore` (`store.py`) is the default for `create_app()` and for the CLI: `cli/main.py:main()` builds an in-memory store when no service is passed, so CLI chats are not persisted and ignore `CHAT_STORE`. Only the web app goes through `create_store()`. In production and local runs, `backend/app/wsgi.py` calls `create_store()` (`stores.py`), which picks the store from `CHAT_STORE`: `duckdb` (default; `DuckDBSessionStore` in `duckdb_store.py`, persisting to `CHAT_DATABASE_PATH`, default `data/chat.duckdb`) or `postgres` (`PostgresSessionStore` in `postgres_store.py`, a `psycopg` connection pool reading `DATABASE_URL`). Use Postgres for production; DuckDB is for local development and single-process use. A new store subclasses `SessionStore`, is selected in `create_store()`, and must pass `tests/test_store_contract.py`, which runs the same checks against every implementation (Postgres only when `TEST_DATABASE_URL` is set). Unknown session IDs raise `KeyError`, and the Flask routes map that to 404. Title derivation (first 48 characters of the first user message, newlines flattened) lives in the base class.

**Key rotation.** `KeyVault.reseal` moves a row sealed by an older `KEY_ENCRYPTION_KEYS` entry onto the current one. `python -m backend.app.rotate_keys [--dry-run]` runs it over every saved key, using `AccountStore.list_all_api_keys` and the compare-and-swap `replace_api_key_seal`, and writes a `rekey` audit event per moved row.

**Configuration loading.** `.env` is loaded from the repo root by `settings.py` and again by `wsgi.py`. `Settings.from_env()` is called lazily inside `ChatService`, so missing config raises at first message, not at import. The CLI catches `RuntimeError` as a configuration error. The web app is the exception: `wsgi.py` builds `AuthConfig` (needs `GOOGLE_CLIENT_ID`, `JWT_SECRET`), `KeyVault` (needs `KEY_ENCRYPTION_KEYS`) and `TokenService` at import, so a missing value stops startup. The web app never reads `ANTHROPIC_API_KEY` or `OPENROUTER_API_KEY`; only the CLI's server-key path does.

**Testing approach.** `tests/support.py` provides `sign_in(client)` (a real signed access cookie for `USER_ID`) and `OTHER_USER_ID`. `tests/conftest.py` sets the auth environment variables and turns rate limits off. Tests inject fakes rather than hitting the network: `FakeProvider` (any object with `stream(...)` that yields events) is passed as `ChatService(provider=...)`. `AnthropicProvider(client=FakeClaudeClient())` covers the Anthropic SDK path, and `FakeChatService` is passed to `create_app(chat_service=...)`. Keep new tests in this style; there is no live-API test.

**Frontend state.** A single React context (`frontend/src/Context.tsx`) holds the active session, session list, `isGenerating`, sidebar state, theme, a toast-style error stack, and the sign-in state (`authStatus`, `currentUser`). The `/settings` page (`SettingsPage.tsx`) sets the provider in use and each provider's key. `AuthGate` shows `LoginPage` until a user is signed in. `api.ts` renews an expired access token once per burst of requests, and dispatches `signed-out` when it cannot. Components read it via `useContext(Context)`. The Vite dev server is the only proxy to Flask, so frontend code uses relative `/api` paths.

**Theming.** Light and dark mode are switched by the `dark` class on `<html>`, which Tailwind keys on (`darkMode: 'class'` in `tailwind.config.js`). `ContextProvider` owns `theme` (`light` | `dark`), saved in localStorage under `ai-chat.theme`; until the user picks one it follows `prefers-color-scheme`. The toggle lives in the sidebar footer. **Every new UI element must work in both themes:** pair each light colour class with a `dark:` variant in the same `className`, and do not add bare `bg-white`, `bg-gray-*`, `text-gray-*`, or `border-gray-*` without one. Use the palette the existing components already use:
- Page `dark:bg-[#131314]`, sidebar `dark:bg-[#1e1f20]`, menus, popovers and modals `dark:bg-[#28292a]`, borders `dark:border-[#3c4043]`
- Hover and button fills `dark:bg-[#303134]` / `dark:hover:bg-[#3c4043]`, menu row hover `dark:hover:bg-[#353638]`
- Primary text `dark:text-[#e3e3e3]`, secondary text `dark:text-[#9aa0a6]`, accent `dark:text-[#8ab4f8]`, red actions `dark:text-red-400`

Two exceptions are intentional: the copied rich-text HTML in `CopyResponseBtn` carries inline light styles so it pastes readably elsewhere, and the code block wrapper is always dark zinc. Check new UI in both themes before finishing.

## Known state

- `npm run build` passes: `tsc -b` reports no type errors and the Vite bundle builds.
- `uv run ruff check .` passes. The CLI catches `ProviderError` (raised by any provider, including when an OpenRouter stream chunk carries an `error`) for request failures, so other exceptions propagate instead of being printed.
- `uv run pytest` passes: 202 passed, 23 skipped without `TEST_DATABASE_URL`; 225 passed with it set to a Postgres database.
- Gunicorn worker limits depend on the store. With `CHAT_STORE=duckdb`, workers must stay at 1: DuckDB takes a write lock, and each worker opens the file at import. Threads are safe there because `DuckDBSessionStore` serializes its public methods with a lock. With `CHAT_STORE=postgres`, each worker has its own connection pool, so more workers or threads are safe. Raising threads needs `--worker-class gthread`, since the `sync` worker ignores `--threads`. The production command in README still uses `--workers 1` as the baseline; raise it only after Postgres is in production.
- The default Gunicorn timeout (30s) is too short for slow model replies, which is why the command sets `--timeout 120`.
- Rate limits (Flask-Limiter, in memory) are counted per process, so with several workers each keeps its own count. Signed-in calls are limited per user, others per IP.
- `wsgi.py` no longer calls `warm_up()`: the web app has no server-wide key to warm up. `warm_up()` remains for the server-key path.
