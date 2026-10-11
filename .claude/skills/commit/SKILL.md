---
name: commit
description: Write a commit message for this repo's changes, mapping each changed folder (backend, core, cli, frontend, tests, docs, config, deps) to its area, then commit the staged changes. Use when the user asks for a commit message or to commit.
---

# Commit message for ai-chatbot

Write the message from the actual diff, not from memory of the session. Commit only when the user has asked for a commit, which invoking this skill counts as.

## 1. Read the changes

Run these in parallel:

```bash
git status --short
git diff --cached --stat
git diff --stat
git log -5 --format='%s'
```

- If something is staged, the commit covers only the staged set. Leave unstaged work out and say so.
- If nothing is staged, the commit covers all tracked changes plus new untracked files. Stage them by explicit path, never with `git add -A` or `git add .`.

## 2. Exclude secrets and generated output

Never stage or commit these. `.gitignore` already covers most of them, but check for files that are not ignored:

- `.env` and `.env.*` (`.env.example` is the only exception and is safe to commit)
- `data/` (DuckDB files, `chat.duckdb` and its `.wal`)
- `.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `frontend/node_modules/`, `frontend/dist/`, `*.tsbuildinfo`
- `.idea/`

If a changed file looks like a credential or local state (API keys, database files, machine-specific paths), stop, name the file, and ask before committing.

## 3. Map folders to areas

Use the area names below in the message. Each row is the first match.

| Changed path | Area |
|---|---|
| `core/chat_core/providers/` | providers (Anthropic, OpenRouter, pricing, or the OpenRouter HTTP wrapper; name the one that changed) |
| `core/chat_core/*_store.py`, `store.py`, `stores.py` | storage (name the store: DuckDB, Postgres, or the base contract) |
| `core/chat_core/service.py`, `models.py`, `settings.py` | core service / settings |
| `backend/` | backend (Flask API, SSE framing, wsgi and gunicorn) |
| `cli/` | CLI |
| `frontend/src/components/` | UI component (name the component, e.g. Sidebar, PromptInput) |
| `frontend/src/` other files (`api.ts`, `Context.tsx`, `speech.ts`, `voiceInput.ts`, `index.css`, ...) | frontend |
| `frontend/public/`, `frontend/*.config.*`, `frontend/package*.json`, `tailwind.config.js` | frontend build or assets |
| `tests/` | tests (name the area under test, e.g. store contract, streaming API) |
| `README.md`, `CLAUDE.md` | docs |
| `pyproject.toml`, `uv.lock` | Python deps |
| `frontend/package-lock.json` | frontend deps |
| `.env.example`, `.gitignore`, `.claude/` | config / tooling |

A commit that touches several areas is normal. Name the main change in the subject and list the rest in the body.

## 4. Write the message

Match the repo's existing style, which has no type prefix such as `feat:` or `fix:`:

- **Subject:** imperative mood, 72 characters or fewer, no trailing period. Name the thing that changed, not the generic activity. Use "Add Postgres session store", not "more features". Use "Fix SSE frame split on blank lines", not "bug fixes". Avoid vague subjects like "UI improvements", "updates", and "improvements", which the recent history is full of.
- **Body:** optional. Add it when the change spans areas or the reason isn't obvious from the diff. Wrap at 72 characters. Use short bullets, one per area, and say why, not just what.
- **Trailer:** end the message with a blank line and this exact line:

  `Co-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>`

Examples of the target shape:

```
Add dark mode toggle to sidebar footer

- frontend: theme state in ContextProvider, persisted under ai-chat.theme
- frontend/components: Sidebar footer toggle with dark variants
- tests: theme persistence has no server coverage, so none added

Co-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>
```

```
Stop persisting assistant message when provider raises

The service saved partial text before the ProviderError was raised,
so retries showed a truncated reply. Save only after the stream ends.

- core/chat_core/service.py: move save after the stream loop
- tests/test_service.py: cover the failure path

Co-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>
```

## 5. Check before committing

- The subject names a specific change, and no area in the diff is missing from the message.
- The Co-Authored-By trailer is present and exact.
- No secret or generated file is in the staged set.

If the repo's checks are relevant to the change, run them first and say what you ran. These are from `CLAUDE.md`:

- Python: `uv run ruff check .` and `uv run pytest`
- Frontend: `npm run build` from `frontend/`

## 6. Commit

Pass the message on stdin so quoting and multi-line bodies stay correct:

```bash
git commit -F - <<'EOF'
<subject>

<body>

Co-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>
EOF
```

Then run `git log -1 --stat` and report the commit hash, subject, and file list. Do not push unless the user asks. If the commit fails because a hook rejected it, report the hook's output and fix the cause. Do not bypass hooks with `--no-verify`.
