# AI Chat

A responsive chat application built with Flask, the Anthropic Python SDK, React, and TypeScript. It supports direct Anthropic access and OpenRouter through the same Anthropic SDK integration.

## Features

- Create, switch, and clear chat sessions
- Stream model replies to the browser and terminal
- Render assistant replies as Markdown, including code blocks, links, and lists
- Use Anthropic or OpenRouter credentials
- Share core chat logic between the Flask API and CLI

## Project structure

```text
backend/     Flask API and production WSGI entry point
cli/         Terminal chat client
core/        Shared session storage, settings, and model service
frontend/    Vite + React browser interface
tests/       Python unit and API tests
```

Chat sessions are currently held in memory. They reset when the backend restarts; use a database-backed store before production use.

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
```

For OpenRouter access through the Anthropic SDK:

```env
AI_PROVIDER=openrouter
OPENROUTER_API_KEY=your_openrouter_key
CLAUDE_MODEL=anthropic/claude-sonnet-4.5
```

`python-dotenv` loads `.env` for local runs. Real environment variables take precedence, so deployment secrets override local values.

## Run locally

Start the Flask API from the repository root:

```bash
uv run flask --app backend.app:create_app run --debug --port 5000
```

In a separate terminal, start the frontend:

```bash
cd frontend
npm run dev
```

Open the displayed Vite URL, normally `http://localhost:5173`. The Vite development server proxies browser requests from `/api` to Flask at `http://127.0.0.1:5000`.

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

Set `AI_PROVIDER`, the provider-specific API key, and `CLAUDE_MODEL` through your hosting platform's secret manager. Do not upload a `.env` file to production.

Run the Flask application with Gunicorn:

```bash
uv sync --frozen
uv run gunicorn --workers 2 --bind 0.0.0.0:5000 backend.app.wsgi:app
```

Place Gunicorn behind an HTTPS-terminating reverse proxy. Before public release, add authentication, rate limiting, restricted CORS origins, observability, backups, and durable user-scoped session storage.
