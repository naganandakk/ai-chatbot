---
name: pg-test-db
description: Create or reset the disposable Postgres test database and run the Postgres store contract tests against it. Use when the user asks to run Postgres tests, the store contract tests, or to set up a local Postgres for testing.
---

# Postgres contract tests

`tests/test_store_contract.py` runs `TRUNCATE chat_messages, chat_sessions` before its checks. Point it only at a database that holds no data anyone keeps. This skill exists to make that safe.

## Safety check first

Before any command, confirm the target database name contains `test`, for example `chat_store_test`.

- If the user gives a name without `test`, refuse and ask them to use a disposable name.
- If the name is `chat_dev` or taken from `DATABASE_URL` in `.env`, refuse. That is the development database.
- Never set `TEST_DATABASE_URL` to the value of `DATABASE_URL`.

## Steps

1. Check that Postgres accepts connections: `psql -c 'select 1' postgres`. If it does not, tell the user to start the server (for example `brew services start postgresql@17`, or the Docker `postgres:17` container). Do not start a server yourself without asking.
2. Create the database if it does not exist:
   `psql -c 'CREATE DATABASE chat_store_test' postgres`
   If it already exists, the error is expected. Say so and continue.
3. Run the contract tests only:
   `TEST_DATABASE_URL=postgresql:///chat_store_test uv run pytest tests/test_store_contract.py -v`
4. Report the pass, skip, and fail counts from the output.

## Cleanup

Do not drop the database unless the user asks. To remove its data, use `TRUNCATE` on the two tables only, and only after the safety check above passes.

## Report

Give the database name used, the command, and the pytest summary line. If a test failed, quote the assertion output. Do not describe a failure as an environment problem without evidence.
