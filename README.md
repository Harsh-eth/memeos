# MemeOS

Agent-driven meme generation MVP: **Planner** → **Caption** → **Template** → **Renderer**, plus an optional **Feed** loop that turns trending topics into memes.

## Folder structure

```
memeos/
  README.md
  backend/
    main.py                 # FastAPI app + routes
    config.py
    trending.py             # Phase-1 static trending (Phase-2: swap provider)
    requirements.txt
    .env.example
    agents/
      planner.py
      caption.py
      template_agent.py
      renderer.py
      feed_agent.py
    services/
      llm.py                # OpenAI JSON/text helpers
    storage/
      feed_store.py
    templates/
      index.json            # written by seed script
      images/*.png
    scripts/
      seed_templates.py     # generates example templates + index.json
  frontend/
    package.json
    vite.config.ts
    tailwind.config.js
    src/
      App.tsx
      api.ts
```

## Prerequisites

- Python 3.11+
- Node 18+
- (Optional) OpenAI API key for real planner/caption reasoning

## Backend

```bash
cd memeos/backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # add OPENAI_API_KEY if you have one
python scripts/seed_templates.py   # optional; also runs on API startup if missing
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### API

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/generate-meme` | Body: `{"prompt":"..."}` → PNG base64 + metadata (plan, captions, reasoning) |
| `GET` | `/feed` | Recent memes (user + auto) |
| `POST` | `/auto-toggle` | Body: `{"enabled": true\|false}` |
| `GET` | `/auto-status` | Current auto mode |
| `GET` | `/trending` | Static trending topics (MVP) |
| `GET` | `/health` | Liveness + whether OpenAI is configured |

### Generate security (strict)

`POST /generate-meme` is locked down:

- **Daily quota**: **5 successful generations per client IP per day** (calendar day on the server). Returns **429** with `Retry-After` when exceeded. Slots are **released** if the pipeline errors so failures do not burn quota.
- **Shared secret**: Header **`X-MemeOS-Client-Token`** must equal **`MEMEOS_CLIENT_TOKEN`** in `.env`. If unset, generate returns **503**. The SPA sends the same value from **`VITE_MEMEOS_CLIENT_TOKEN`**.
- **Intent header**: **`X-MemeOS-Intent: generate`** must be present (only the app’s `generateMeme()` sets this).
- **Content-Type**: **`application/json`** required.
- **User-Agent**: Non-empty and minimum length; common **CLI/automation** patterns (curl, wget, httpx, Postman, etc.) are rejected when **`BLOCK_CLI_USER_AGENTS=true`**.
- **Origin / Referer**: When **`REQUIRE_ORIGIN_OR_REFERER=true`**, one of them must match **`CORS_ORIGINS`** (stops bare `curl` to the API without a browser context).
- **Optional**: **`REQUIRE_SEC_FETCH_SITE_BROWSER=true`** enforces `Sec-Fetch-Site` ∈ {`same-origin`, `same-site`}. **`TRUST_PROXY_FOR_IP=true`** uses `X-Forwarded-For` (only behind a **trusted** reverse proxy). **`RATE_LIMIT_EXEMPT_IPS`** skips the daily cap for listed IPs (dev only).

Other routes (`/feed`, etc.) are unchanged. For multi-instance production, replace the in-memory limiter with Redis.

## Frontend

```bash
cd memeos/frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). The dev server proxies API calls to `http://127.0.0.1:8000`.

Copy `frontend/.env.example` → `.env` and set **`VITE_MEMEOS_CLIENT_TOKEN`** to the same value as backend **`MEMEOS_CLIENT_TOKEN`** (see backend `.env.example`).

## Behavior notes

- **Without `OPENAI_API_KEY`**, planner and caption agents use **deterministic mock** output so the stack runs fully offline.
- **Auto mode** runs a background asyncio loop (interval `AUTO_INTERVAL_SECONDS`) that picks a random static trending string, runs the same pipeline, and appends to the feed.
- **Phase 2 trending**: replace `get_trending()` in `backend/trending.py` with Twitter/Telegram sources; the feed agent only depends on `list[str]`.

## Production hints

- Serve the built frontend as static files or behind a CDN; set `CORS_ORIGINS` to your domain.
- Persist `feed_store` to Redis/Postgres instead of in-memory for multi-instance deployments.
- Rate-limit `/generate-meme` and cap image size/fonts in `renderer.py` as needed.
