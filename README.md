# AI Chat

A responsive chat application built with Flask, the Anthropic Python SDK, React, and TypeScript. It supports direct Anthropic access through the Anthropic SDK and OpenRouter through the OpenRouter SDK.

## Features

- Create, switch, and clear chat sessions
- Stream model replies to the browser and terminal
- Render assistant replies as Markdown, including code blocks, links, and lists
- Use Anthropic or OpenRouter credentials
- Share core chat logic between the Flask API and CLI
- Persist web chat sessions in DuckDB

## Web interface features

Sessions and sidebar

- Start a new chat from the **New Chat** button in the sidebar
- Open any saved chat from the sidebar list; the most recent chat opens on load
- Per-chat menu (three-dot icon on hover): **Rename**, **Clear History**, and **Delete**
- Rename a chat inline with the check and cancel buttons
- The sidebar collapses with the menu icon and opens automatically on wide screens; on narrow screens it opens as an overlay and closes when you click outside it or pick a chat
- Chat titles come from the first message, truncated to 48 characters

Composing and replies

- Type a prompt in the input box and press Enter or the send button
- Replies stream in as they are generated, with a loading indicator before the first text arrives
- When the chat is scrolled away from the latest message, a down-arrow button appears above the prompt box; click it to jump to the bottom
- Attach files with the paperclip button, drag them onto the prompt, or paste them. Images (PNG, JPEG, GIF, WebP), PDFs, and text or code files are accepted. Files stay with the chat, and images preview in the message
- Attachment limits are set by `MAX_ATTACHMENT_MB` (each file, default 5), `MAX_ATTACHMENTS_PER_MESSAGE` (default 5), `MAX_ATTACHMENTS_TOTAL_MB` (all files in one prompt, default 10), and `MAX_SESSION_ATTACHMENTS_MB` (all files in one chat, default 20). The defaults fit the model APIs' per-request size limits; see `.env.example`
- Send is disabled while a reply is in progress or when the prompt is empty and has no files
- Empty chats show starter prompts; click one to fill the input box
- Assistant replies render Markdown, including code blocks, tables, headings, and lists
- Errors appear as toast notifications in the top-right corner and can be dismissed

Per-message actions

- **Copy message**: click a user message to reveal a copy button for that message
- **Copy response**: copies an assistant reply as rich text, keeping formatting, and as plain text
- **Code block copy**: each code block has its own copy button
- **Sources**: shown under an assistant reply when the model cites web sources; click to see each title and link, which open in a new tab
- **More options** (three-dot icon under an assistant reply):
  - **Listen** reads the reply aloud with the browser's speech synthesis, then changes to **Pause** while it plays and **Resume** after pausing
  - Starting another message's Listen stops the one already playing
  - While audio plays, a pause/resume icon button appears at the top right of the chat area, whichever message is playing; it disappears when playback ends
  - Switching to another chat, or starting a new chat, stops playback
  - The footer shows the model that produced the reply, or `Unknown` for replies saved before model tracking was added
  - The menu opens above the button when there is not enough room below it in the chat area

Appearance

- Light and dark themes. Toggle **Dark mode** in the sidebar footer (on phones the sidebar closes after the switch). The choice is saved in the browser; until one is chosen, the app follows the operating system's light or dark setting
- Every part of the interface has both themes. When adding UI, give each light colour class a `dark:` counterpart (see the theming notes in `CLAUDE.md`)
- The layout adapts to narrow and wide screens

Listen depends on the browser having a speech synthesis voice. If none is available, playback has no sound.

## Project structure

```text
backend/     Flask API and production WSGI entry point
cli/         Terminal chat client
core/        Shared session storage, settings, and model service
frontend/    Vite + React browser interface
tests/       Python unit and API tests
data/        Local DuckDB database directory, created at runtime
```

The web application stores sessions in DuckDB by default. The default database path is `data/chat.duckdb`, so sessions survive backend restarts on the same machine. Set `CHAT_STORE=postgres` and `DATABASE_URL` to use PostgreSQL instead (see [Production deployment](#production-deployment)).

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

The web app needs these to start:

```env
GOOGLE_CLIENT_ID=your_client_id.apps.googleusercontent.com
JWT_SECRET=a_random_string_of_at_least_32_characters
KEY_ENCRYPTION_KEYS=base64_32_byte_key
CHAT_DATABASE_PATH=data/chat.duckdb
```

Generate `JWT_SECRET` with `openssl rand -base64 48`, and `KEY_ENCRYPTION_KEYS` with:

```bash
python -c "import secrets,base64;print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

Each user adds their own Anthropic or OpenRouter API key in the app (**Settings** in the sidebar). Choose the provider in use there too; the first key you save is selected automatically.. Replies are billed to that key, so the server does not need a provider key for the web app.

The terminal client has no sign-in and uses the server's own key from `.env`:

```env
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=your_anthropic_key
CLAUDE_MODEL=claude-sonnet-4-5
```

For OpenRouter instead, set `AI_PROVIDER=openrouter` and `OPENROUTER_API_KEY`.

`python-dotenv` loads `.env` for local runs. Real environment variables take precedence, so deployment secrets override local values.

### Google sign-in

1. In Google Cloud Console, create an OAuth client ID of type **Web application**.
2. Under **Authorized JavaScript origins**, add each origin the app is opened from, for example `http://localhost:5173` and, for phone testing, the HTTPS LAN origin from `npm run dev:lan`. Plain `http://` LAN addresses are not accepted by Google.
3. Put the client ID in `.env` as `GOOGLE_CLIENT_ID`, and in `frontend/.env.local` as `VITE_GOOGLE_CLIENT_ID` for the sign-in button.

Optional sign-in limits in `.env`: `ALLOWED_EMAILS` (comma-separated), `ALLOWED_EMAIL_DOMAINS`, and `COOKIE_SECURE=false` for plain-HTTP runs. Cookies are `Secure` by default, so they are not sent over plain HTTP.

The first account to sign in takes ownership of any chats that were created before accounts existed.

**Rotating the encryption key:** put the new key first in `KEY_ENCRYPTION_KEYS` and keep the old one after it. New keys are sealed with the first entry, and older rows still open with the older one. Then move the saved keys onto the new one (stop the app first if `CHAT_STORE=duckdb`):

```bash
uv run python -m backend.app.rotate_keys --dry-run   # count rows that would move
uv run python -m backend.app.rotate_keys             # re-seal them; exits 1 if any row cannot be opened
```

Once the run reports `failed=0`, remove the old key from `KEY_ENCRYPTION_KEYS`. A row sealed by a key that was removed cannot be recovered, and its user has to save the provider key again.

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

Sign-in needs `VITE_GOOGLE_CLIENT_ID` in `frontend/.env.local`, and the origin you open must be listed in the Google client (see [Google sign-in](#google-sign-in)).

To use voice prompts from a phone on your network, see [Use voice prompts from a phone on the local network](#use-voice-prompts-from-a-phone-on-the-local-network).

### Use voice prompts from a phone on the local network

Browsers only allow the microphone on HTTPS or `localhost`, so voice prompts do not work when the phone opens `http://<your-ip>:5173`. To serve the dev server over HTTPS on your LAN, create a local certificate with [mkcert](https://github.com/FiloSottile/mkcert) (`brew install mkcert` on macOS):

```bash
mkcert -install                       # once per machine: trusts the local CA on this Mac
cd frontend
mkdir -p certs
mkcert -cert-file certs/lan.pem -key-file certs/lan-key.pem <your-lan-ip> localhost 127.0.0.1
```

Find your LAN IP with `ipconfig getifaddr en0` (or `en1` on Wi-Fi on some Macs). Then start the frontend with the flag:

```bash
npm run dev:lan
```

To check other features on a phone without HTTPS, run `npm run dev:network`. It serves plain HTTP on the LAN, so voice prompts will not work through it.

`dev:lan` runs `LAN_HTTPS=1 vite --host`, which serves HTTPS on the LAN. The script uses a POSIX environment variable, so on Windows set `LAN_HTTPS=1` in your shell first or run `npx vite --host` with the variable set.

Vite prints a `Network:` URL such as `https://192.168.1.23:5173`. To trust the certificate on a phone:

- **iPhone:** AirDrop or email `rootCA.pem` (run `mkcert -CAROOT` to find it), install it under Settings > General > VPN & Device Management, then enable full trust under Settings > General > About > Certificate Trust Settings.
- **Android:** copy `rootCA.pem` to the phone and install it under Settings > Security > Encryption & credentials > Install a certificate > CA certificate.

If your IP changes, run the `mkcert` command again with the new IP. The `frontend/certs/` folder is ignored by git. Without `LAN_HTTPS=1`, Vite serves plain HTTP on `localhost` only, as before.

DuckDB holds a write lock on its database file. Flask's debug reloader starts a second process, which would compete for that lock, so use `--no-reload`. Stop any existing Flask process before starting another server against the same database file.

## Run the terminal client

```bash
uv run python -m cli.main
```

The terminal client keeps its sessions in memory and ignores `CHAT_STORE`, `CHAT_DATABASE_PATH`, and `DATABASE_URL`. Its chats are not saved to DuckDB or Postgres and disappear when the process exits. Use the web app when you need persistent sessions.

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

Set `GOOGLE_CLIENT_ID`, `JWT_SECRET`, `KEY_ENCRYPTION_KEYS`, and the storage variables below through your hosting platform's secret manager. Do not upload a `.env` file to production. Provider keys are supplied by users in the app, not by the server.

Sign-in cookies are `Secure`, so serve the app over HTTPS. The API uses same-origin requests only, so no CORS origins need configuring.

Choose the session store with `CHAT_STORE`:

- `CHAT_STORE=postgres` with `DATABASE_URL=postgresql://user:password@host:5432/dbname` for production. Sessions live in the database server, so the application can run with several workers or threads.
- `CHAT_STORE=duckdb` (the default) with `CHAT_DATABASE_PATH` for local development. Store the DuckDB file on persistent storage; ephemeral filesystem storage will erase sessions when the deployment restarts.

The Postgres tables are created on first start. To run the store contract tests against a Postgres database, set `TEST_DATABASE_URL` to a disposable database. The tests empty its tables before each check.

Run the Flask application with Gunicorn:

```bash
uv sync --frozen
uv run gunicorn --workers 1 --timeout 120 --bind 0.0.0.0:5000 backend.app.wsgi:app
```

Keep these settings in mind:

- A message with files is a multipart upload. With the default limits a request can be up to about 11 MB, and the 120-second Gunicorn timeout leaves room for the upload and a slow reply.
- With `CHAT_STORE=duckdb`, `--workers 1` is required. `backend.app.wsgi` opens the DuckDB file when it is imported, and DuckDB takes a write lock, so a second worker cannot open the same file. With `CHAT_STORE=postgres`, each worker opens its own connection pool, so more workers are safe.
- The default worker class is `sync`, which serves one request at a time. A streaming reply holds the worker until it finishes, so other requests wait. The store serializes its DuckDB calls with a lock, so threads are safe to use. Raising `--threads` also needs `--worker-class gthread`, because the `sync` worker ignores it.
- `--timeout 120` replaces Gunicorn's default of 30 seconds. A sync worker does not report progress while handling a request, so a slow model reply could otherwise get the worker killed. Set this to the longest reply you expect.

DuckDB is appropriate for one backend process. Do not run multiple Gunicorn workers or multiple application instances against the same write-enabled DuckDB file. For horizontal scaling or higher write concurrency, migrate session storage to PostgreSQL.

Place Gunicorn behind an HTTPS-terminating reverse proxy. The proxy must send `Strict-Transport-Security: max-age=31536000; includeSubDomains`, since Flask cannot see the scheme. The static host that serves `frontend/dist/` should send the same `Content-Security-Policy` that the production build puts in its meta tag (see `frontend/vite.config.ts`). Flask already sends the API headers (`no-store`, `nosniff`, frame denial, and a restrictive CSP). Key saves and deletes are recorded in the `audit_events` table, without the key. Before public release, add observability and backups.

Rate limits (sign-in, token refresh, saving API keys, and sending messages) are counted in memory per process. With several Gunicorn workers each one keeps its own count, so the effective limit is the configured number times the worker count. Set `RATE_LIMIT_ENABLED=false` only for local testing.
