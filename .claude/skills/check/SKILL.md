---
name: check
description: Run this repo's full verification gate (ruff, pytest, frontend build, optional Postgres contract tests) and report each step's result. Use before committing, before opening a PR, or when the user asks to check, verify, or test the changes.
---

# Verification gate for ai-chatbot

Run the gate from the repo root. Report each step's result from its real output. Do not claim a step passed unless it did.

## Steps

Run in this order. Stop at the first failure only if a later step depends on it. Otherwise run all steps and collect results.

1. Lint: `uv run ruff check .`
2. Python tests: `uv run pytest`
3. Frontend build: `cd frontend && npm run build` (runs `tsc -b` then `vite build`)
4. Postgres contract tests, only if `TEST_DATABASE_URL` is set in the environment or `.env`:
   `TEST_DATABASE_URL=... uv run pytest tests/test_store_contract.py`

If `node_modules` is missing in `frontend/`, run `npm install` first and say so. If `.venv` is missing, run `uv sync --all-groups` first.

## Reporting

For each step, state:
- the command run
- pass or fail, with the pass/skip/fail counts from pytest
- on failure, the first relevant error block, quoted

The Postgres step is skipped when `TEST_DATABASE_URL` is unset. Say it was skipped. Do not present a skip as a pass.

Reference counts from `CLAUDE.md` at the time it was written: 109 passed and 14 skipped without `TEST_DATABASE_URL`, and 123 passed with it. Counts drift as tests are added, so report the actual numbers and only flag a difference if the failures or skips are unexplained.

## Do not

- Do not use `--no-verify`, skip failing tests, or edit tests to make them pass without telling the user.
- Do not run the Flask server or the dev server. Use the `run` skill for that.
- Do not point `TEST_DATABASE_URL` at a database holding data you keep. The contract tests `TRUNCATE` its tables.
