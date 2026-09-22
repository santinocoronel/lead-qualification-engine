# AI Context Engine

B2B SaaS platform — intelligent middleware between developers and LLMs. Users configure their tech stack, define architecture rules, provide their own API key (BYOK), and get production-ready code streamed via SSE.

## Tech Stack

- **Backend:** Python 3.14, FastAPI, Pydantic v2, SQLAlchemy 2.0 Async + asyncpg
- **Database:** Supabase PostgreSQL
- **Auth:** JWT (PyJWT + bcrypt), BYOK keys encrypted with Fernet
- **LLM Providers:** OpenAI, Anthropic, Google Gemini, DeepSeek, Mistral (all via OpenAI-compatible protocol where possible)
- **Email:** Resend HTTP API
- **Payments:** LemonSqueezy (webhooks for subscription lifecycle)
- **Deploy:** Docker multi-stage build, Gunicorn + UvicornWorker on Render
- **Frontend:** Vanilla HTML/CSS/JS (static files served by FastAPI)

## Architecture

Clean Architecture / Hexagonal: Domain → Application → Infrastructure → API

```
src/
├── domain/           # Entities, value objects, enums
├── application/      # Use cases, prompt assembler
├── infrastructure/   # LLM streaming, persistence, email, crypto
└── api/              # FastAPI routers, middleware
static/               # Landing page, dashboard, checkout
tests/                # Unit tests (87+ passing)
```

## Key Files

- `src/infrastructure/llm/streaming_factory.py` — LLM routing, provider specs, model registry
- `src/api/v1/generate_router.py` — Code generation & review endpoints, config API
- `src/api/v1/billing_router.py` — LemonSqueezy/PayPro webhooks, checkout
- `src/api/v1/auth_router.py` — Register, login, forgot/reset password, BYOK
- `static/dashboard.html` — Main app UI (auth, code gen, review, history, settings)
- `static/index.html` — Landing page with pricing
- `static/checkout.html` — Payment checkout flow

## Environment

- Render service ID: `srv-dao9taek1f9s73b83kk0`
- Live URL: https://lead-qualification-engine-4ltk.onrender.com
- GitHub: santinocoronel/lead-qualification-engine

## Plan Tiers

| Plan   | Price   | Generations/mo |
|--------|---------|----------------|
| Free   | $0      | 100            |
| Pro    | $49/mo  | 5,000          |
| Agency | $199/mo | 25,000         |

## Commands

```bash
# Run tests
python -m pytest tests/ -x -q

# Run locally
docker compose up --build

# Deploy (auto on push to main via Render)
git push origin main
```

## Safety Rules

- Never delete production data or tables
- Never force-push to main
- Never expose API keys, secrets, or .env contents
- Always run tests before pushing
- Prefer editing existing files over creating new ones
