---
name: new-store
description: Scaffold a new SessionStore implementation for ai-chatbot, wire it into create_store() and the contract tests. Use when the user asks to add a storage backend, such as SQLite, Redis, or another database.
---

# Add a session store

Read these first, because they define the contract:
- `core/chat_core/store.py` (`SessionStore` ABC: create, get, list, add_message, clear, delete, update, close)
- `core/chat_core/stores.py` (`STORE_NAMES`, `create_store()`)
- `core/chat_core/duckdb_store.py` (the reference for a local store and its lock)
- `core/chat_core/postgres_store.py` (the reference for a pooled, multi-process store)
- `tests/test_store_contract.py` (the checks every store must pass)
- `tests/test_stores.py` (the selection tests for `create_store()`)

## Rules

- Subclass `SessionStore`. Title derivation (first 48 characters of the first user message, newlines flattened) lives in the base class. Do not reimplement it.
- Unknown session IDs raise `KeyError`. The Flask routes map that to 404.
- If the store is safe to share across threads, serialize public methods with a lock, as `DuckDBSessionStore` does. If it is not, say so in the docstring and in the answer.
- Gunicorn worker limits depend on the store. Record the new store's limits in your report. Do not change the README production command.
- Do not import the new store from `cli/`. The CLI uses `InMemorySessionStore`.

## Steps

1. Create `core/chat_core/<name>_store.py` with a class that subclasses `SessionStore` and implements every abstract method.
2. Add its name to `STORE_NAMES` in `stores.py` and add a branch in `create_store()`. Read configuration from environment variables following the existing pattern (`CHAT_DATABASE_PATH`, `DATABASE_URL`). Raise `RuntimeError` for missing required config.
3. Add the store to the parametrized list in `tests/test_store_contract.py`. Copy the skip pattern used for Postgres if the store needs an external service. Use a `skipif` on a clearly named environment variable.
4. Add selection tests in `tests/test_stores.py`: the new name selects the new class, and a missing required variable raises.
5. Run `uv run pytest tests/test_store_contract.py tests/test_stores.py`. If the store needs an external service, also run the contract tests against it with the same env var pattern, and state the result.
6. Run `uv run ruff check .`.

## Report

List the store class, the environment variables it reads, whether it is thread-safe, and the test results. If the store was not run against a real service, say the contract tests were skipped.
