---
name: gunicorn-check
description: Validate a Gunicorn command, Dockerfile, or deployment config against the worker and thread rules for each CHAT_STORE backend. Use when changing server startup, worker or thread counts, timeouts, or the production command in README, or when the user asks whether a server config is safe.
---

# Gunicorn worker and thread check

The safe worker count depends on the store, as stated in `CLAUDE.md`:

- `CHAT_STORE=duckdb`: `--workers` must be 1. DuckDB takes a write lock on the file, and each worker opens it at import. Threads are safe because `DuckDBSessionStore` serializes its public methods.
- `CHAT_STORE=postgres`: more workers or threads are safe, because each worker has its own connection pool.
- `--threads` is ignored by the `sync` worker. Raising threads needs `--worker-class gthread`.
- The default timeout is 30s. Model replies can be slow, so the production command sets `--timeout 120`.
- The README production command uses `--workers 1` as the baseline. Raise it only after Postgres is in production. Do not raise it on a change request alone.

## Steps

1. Find every server config in scope: `grep -rn "gunicorn" --include='*.md' --include='*.toml' --include='*.yml' --include='*.yaml' --include='Dockerfile*' --include='Procfile' --include='*.sh' .` and read `backend/app/wsgi.py` for the store wiring.
2. For each config, read the `CHAT_STORE` value it sets. If it is not set, the default is `duckdb`.
3. Check the rules above against each config:
   - duckdb plus `--workers` greater than 1: fail
   - `--threads` set with the default `sync` worker class: fail, unless `--worker-class gthread` is also set
   - `--timeout` missing or below 120 for the chat endpoint: warn
   - postgres with a worker or thread count above 1: pass, but confirm `DATABASE_URL` is set
4. Check that `wsgi.py` still calls `create_store()` and does not construct a store directly.

## Report

Give a table with one row per config: file, store, workers, threads, worker class, timeout, and result (pass, warn, or fail). For each fail, quote the line and give the one-line fix. Do not edit a production config without asking.

If you run gunicorn locally to verify it, say which store and command you used. Use `--no-reload` with Flask on duckdb, as `CLAUDE.md` requires.
