---
name: sse-contract
description: Keep the server-sent event framing between backend/app/__init__.py and frontend/src/api.ts in sync. Use when changing SSE event names, data shapes, frame separators, or the stream routes, or when the user reports streaming bugs in the chat UI.
---

# SSE contract between backend and frontend

The stream format is a two-file contract. Any change must be made on both sides in the same change.

- Server: `backend/app/__init__.py`, the `generate()` function inside `send_message`. It frames `ChatService.stream_reply()` output.
- Client: `frontend/src/api.ts`, `streamMessage()`. It splits the buffer on `\n\n`, finds the `data:` line in each frame, and dispatches on the `event:` line.

## Events as implemented

Read the code before relying on this table. These are the events as of the last update:

| Event | Server data | Client action |
|---|---|---|
| `delta` | `{"text": "<chunk>"}` | No `event:` branch. Any frame whose payload has a truthy `text` field calls `onDelta(text)`. |
| `reset` | `{}` | `onReset()`. Sent when `stream_reply` yields a `ReplyReset`, so the client discards partial text. |
| `done` | `{"message": <reply dict>, "session": <summary with usage>}` | `onDone(payload)`. Ends the stream. |
| `error` | `{"message": <string>, "session": <session dict or null>}` | Throws `StreamError(message, session)`. The caller shows the message. |

Important details:

- **Delta has no event name check.** The client decides a frame is a delta by the absence of the other branches plus a truthy `text`. A new event with a `text` field would be treated as a delta. A new event without `text` is silently ignored. Keep this in mind when adding events.
- **Error message mapping on the server.** `KeyError`, `ValueError`, and `TruncatedReplyError` send their own message. Any other exception sends the generic "The model could not respond. Please try again." and logs the traceback.
- **`reset` is not documented in `CLAUDE.md`,** which lists only `delta`, `done`, and `error`. Flag this to the user if it is still true.
- **Framing is safe because of JSON escaping.** `json.dumps` escapes newlines in text, so a `\n\n` inside a delta cannot split a frame. Do not switch to raw text in `data:` lines.

## Steps

1. Read the diffs with `git diff -- backend/app/__init__.py frontend/src/api.ts`, or read the current code if nothing has changed.
2. For each event, confirm the server and client agree on the event name, the JSON keys, and the types. Check `done` and `error` specifically: the client reads `payload.session` and `payload.message`, so renaming either key on the server breaks the UI.
3. Check the dispatch order in `api.ts`. The `error` check runs before the others and throws. If a new event is added, add an explicit `event.startsWith(...)` branch rather than relying on the `text` fallthrough.
4. Check framing. Each frame ends in `\n\n`, and the client keeps the trailing partial frame in `pending`. Do not change that logic without a test.
5. Check the stream ends. The client returns only when `done` is true on the reader. A server path that yields neither `done` nor `error` leaves the UI waiting, so confirm every exit path of `generate()` emits one of them.
6. The CLI does not parse SSE. Check `cli/main.py` only if `ChatService` output shape changed.
7. Run `uv run pytest tests/test_streaming_api.py` and `npm run build` from `frontend/`.

## Report

State the events and fields you verified on each side, with file and line references. Name any mismatch and whether you fixed it. If you did not run a stream in the browser, say that reading the code is not the same as a live check.

## Do not

- Do not change one side only.
- Do not add an event without a matching branch in `api.ts`.
- Do not rely on the `text` fallthrough for any new event.
