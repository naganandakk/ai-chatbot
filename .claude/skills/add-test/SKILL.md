---
name: add-test
description: Write a pytest test for ai-chatbot in the repo's existing fake-based style, using FakeProvider, FakeChatService, FakeClaudeClient, and the in-memory or test store, with no network calls. Use when the user asks to add, write, or cover a test for backend, core, or CLI code.
---

# Add a test in the repo's style

Read two or three existing tests in the same area before writing one. Match their imports, fixtures, and naming.

Relevant files:
- `tests/test_service.py` (`FakeProvider` passed as `ChatService(provider=...)`)
- `tests/test_streaming_api.py` (`FakeChatService` passed to `create_app(chat_service=...)`)
- `tests/test_cli.py` (CLI tests)
- `tests/test_sessions.py` (store behaviour through the API)
- `tests/test_settings.py` (environment-based config)

## Rules

- No network. Inject a fake. There is no live-API test in this repo, and you should not add one.
- A `FakeProvider` is any object with `stream(...)` that yields `TextDelta` or `Citation` events.
- Use `InMemorySessionStore` for store-facing tests unless the test is about a specific store.
- Name tests `test_<behaviour>`, describing the outcome, for example `test_stream_reply_saves_user_and_assistant_messages`.
- Assert on behaviour: saved messages, yielded events, HTTP status codes. Avoid asserting on private attributes.
- Keep tests short. One behaviour per test.

## Steps

1. Find the module under test and the closest existing test file. Read the fakes it uses.
2. Write the test in that file, or create `tests/test_<area>.py` if no file fits.
3. Run only the new test first: `uv run pytest <path>::<name> -v`.
4. Run `uv run pytest` and `uv run ruff check .`.
5. If the test is for a bug fix, confirm it fails without the fix. Say how you checked, or say you did not.

## Report

Give the test name and file, what it asserts, and the test results. Note any fake you had to add and why.
