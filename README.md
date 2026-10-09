# AI Chat

A responsive chat application built with Flask, the Anthropic Python SDK, React, and TypeScript. It supports direct Anthropic access and OpenRouter through the same Anthropic SDK integration.

## Features

- Create, switch, and clear chat sessions
- Stream model replies to the browser and terminal
- Render assistant replies as Markdown, including code blocks, links, and lists
- Use Anthropic or OpenRouter credentials
- Share core chat logic between the Flask API and CLI
- Persist web chat sessions in DuckDB

## Project structure

```text
backend/     Flask API and production WSGI entry point
cli/         Terminal chat client
core/        Shared session storage, settings, and model service
frontend/    Vite + React browser interface
tests/       Python unit and API tests
data/        Local DuckDB database directory, created at runtime
```

The web application stores sessions in DuckDB. The default database path is `data/chat.duckdb`, so sessions survive backend restarts on the same machine.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Node.js 20+
- An Anthropic or OpenRouter API key

## Local setup

Install the Python dependencies from the repository root:

```bash
uv sync --all-groups
```

Install the frontend dependencies:

```bash
cd frontend
npm install
cd ..
```

Create a `.env` file in the repository root. It is ignored by Git and must never contain placeholder values in committed files.

For direct Anthropic access:

```env
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=your_anthropic_key
CLAUDE_MODEL=claude-sonnet-4-5
CHAT_DATABASE_PATH=data/chat.duckdb
```

For OpenRouter access through the Anthropic SDK:

```env
AI_PROVIDER=openrouter
OPENROUTER_API_KEY=your_openrouter_key
CLAUDE_MODEL=anthropic/claude-sonnet-4.5
CHAT_DATABASE_PATH=data/chat.duckdb
```

`python-dotenv` loads `.env` for local runs. Real environment variables take precedence, so deployment secrets override local values.

## Run locally

Start the Flask API from the repository root:

```bash
uv run flask --app backend.app.wsgi:app run --debug --no-reload --port 5000
```

In a separate terminal, start the frontend:

```bash
cd frontend
npm run dev
```

Open the displayed Vite URL, normally `http://localhost:5173`. The Vite development server proxies browser requests from `/api` to Flask at `http://127.0.0.1:5000`.

DuckDB holds a write lock on its database file. Flask's debug reloader starts a second process, which would compete for that lock, so use `--no-reload`. Stop any existing Flask process before starting another server against the same database file.

## Run the terminal client

```bash
uv run python -m cli.main
```

Available commands:

```text
/new
/clear
/quit
```

## Tests and checks

Run the Python test suite:

```bash
uv run pytest
```

Build the frontend for production:

```bash
cd frontend
npm run build
```

## Production deployment

Build the React interface:

```bash
cd frontend
npm ci
npm run build
```

Deploy `frontend/dist/` to a static host, CDN, or reverse proxy. Configure it to serve the frontend and route `/api` requests to the Flask service.

Set `AI_PROVIDER`, the provider-specific API key, `CLAUDE_MODEL`, `CHAT_DATABASE_PATH`, and optionally `TOOLS_ENABLED` through your hosting platform's secret manager. Do not upload a `.env` file to production. Store the DuckDB file on persistent storage; ephemeral filesystem storage will erase sessions when the deployment restarts.

Run the Flask application with Gunicorn:

```bash
uv sync --frozen
uv run gunicorn --workers 1 --timeout 120 --bind 0.0.0.0:5000 backend.app.wsgi:app
```

Keep these settings in mind:

- `--workers 1` is required. `backend.app.wsgi` opens the DuckDB file when it is imported, and DuckDB takes a write lock, so a second worker cannot open the same file.
- The default worker class is `sync`, which serves one request at a time. A streaming reply holds the worker until it finishes, so other requests wait. Do not raise `--threads` yet: the store shares one DuckDB connection across requests, and that connection is not safe to use from multiple threads.
- `--timeout 120` replaces Gunicorn's default of 30 seconds. A sync worker does not report progress while handling a request, so a slow model reply could otherwise get the worker killed. Set this to the longest reply you expect.

DuckDB is appropriate for one backend process. Do not run multiple Gunicorn workers or multiple application instances against the same write-enabled DuckDB file. For horizontal scaling or higher write concurrency, migrate session storage to PostgreSQL.

Place Gunicorn behind an HTTPS-terminating reverse proxy. Before public release, add authentication, rate limiting, restricted CORS origins, observability, and backups.
