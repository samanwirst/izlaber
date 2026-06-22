# AGENTS.md

## Purpose

Izlaber is a Telegram marketplace aggregator. It stores normalized marketplace catalog data, lets users search product cards by text, photo, or voice, and keeps parser ingestion separate from bot runtime.

The repository has three main services:

- `bot/`: aiogram 3 Telegram bot. It talks to the server API only.
- `server/`: Django + DRF API, catalog storage, search, crawl ingestion, and migrations.
- `site/`: Next.js analytics dashboard. It talks to the server API from server-side code only.
- `parsers/uzum_market/`: standalone crawler pipeline that writes products through internal server endpoints.

## Stack

- Python 3.11+ project metadata in `pyproject.toml`; Docker images currently use Python 3.13.
- Django 5.2, Django REST Framework, drf-spectacular.
- aiogram 3, aiohttp, python-dotenv.
- PostgreSQL for production-sized data; SQLite fallback for direct local runs.
- Next.js 16 + React 19 analytics site under `site/`.
- Ruff for linting; pytest, pytest-django, and pytest-asyncio for tests.

## Important Paths

| Path | Purpose |
| --- | --- |
| `bot/handlers/` | Telegram command, message, photo, voice, guest, and admin handlers. |
| `bot/services/` | Server API client, OpenAI helpers, search state, billing/runtime monitors. |
| `bot/locales.py` | Uzbek/Russian/English bot copy, button labels, product labels, language helpers. |
| `server/apps/catalog/` | Product, marketplace, category, user preference models and read/search API. |
| `server/apps/crawling/` | Parser ingestion API, crawl run tracking, product upsert/deactivation services. |
| `site/` | Next.js analytics dashboard for aggregated bot/search/product events. |
| `server/apps/*/migrations/` | Django migrations. Commit migrations with model changes. |
| `parsers/uzum_market/` | Browser/GraphQL crawler, normalizer, checkpoints, parser CLI. |
| `scripts/` | Operational wrappers for Docker, parser runs, audit, and search/visual index rebuilds. |
| `.parser_state/` | Local parser runtime profile/checkpoints. Ignored; do not commit. |

## Commands

Setup:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Local development:

```bash
PYTHONPATH=server python server/manage.py migrate
PYTHONPATH=server python server/manage.py runserver 0.0.0.0:8000
python -m bot
./scripts/docker-start.sh server bot
cd site && npm install && npm run dev
```

Lint and formatting:

```bash
.venv/bin/ruff check .
```

No dedicated repo-wide formatter command is documented. If formatting is needed, keep it scoped and use Ruff consistently:

```bash
.venv/bin/ruff format <paths>
```

Typecheck:

```bash
cd site && npm run typecheck
```

No dedicated Python typecheck command or mypy/pyright config exists yet.

Tests:

```bash
PYTHONPATH=server:. .venv/bin/pytest
PYTHONPATH=server:. .venv/bin/pytest server/tests/test_bot_locales.py
PYTHONPATH=server:. .venv/bin/pytest parsers/uzum_market/test_normalizer.py
```

Build:

```bash
docker compose build server bot parser
docker compose build server bot site parser
docker compose up --build server bot site
```

Database and maintenance:

```bash
PYTHONPATH=server python server/manage.py makemigrations
PYTHONPATH=server python server/manage.py migrate
./scripts/rebuild_product_search_index.sh --marketplace uzum
./scripts/rebuild_product_visual_index.sh --marketplace uzum
./scripts/audit_uzum_catalog.sh --require-checkpoint
```

## Engineering Conventions

- Keep boundaries strict: bot never imports Django models or parser code; parser never writes the database directly; server does not import bot/parser runtime code.
- Bot data access goes through `bot.services.api_client.ServerAPIClient` using `X-Internal-API-Key`.
- Parser ingestion goes through `server/apps/crawling/` endpoints using `PARSER_API_KEY`.
- Analytics site data fetching must stay server-side in `site/lib/`; never expose `BOT_API_KEY` or `ANALYTICS_API_KEY` to browser components.
- User-facing Telegram copy is centralized in `bot/locales.py`; update Uzbek, Russian, and English together.
- When code changes alter setup, commands, API contracts, env vars, data behavior, or agent workflow, update the relevant README or `docs/agents/*` file in the same change.
- Bot pagination state is in `bot/services/search_state.py`; persistent user preferences live in server DB via `UserPreference`.
- Product search behavior is split between `server/apps/catalog/search.py`, visual search/index code, and optional bot-side AI reranking.
- Use Python logging for operational failures. Do not print secrets, raw tokens, or `.env` values.

## Verification Policy

- Documentation-only changes: run `.venv/bin/ruff check <touched python paths>` only if Python files changed; otherwise run `git diff --check`.
- Small bot changes: run Ruff on touched bot files and a focused pytest target such as `server/tests/test_bot_ai.py` or `server/tests/test_bot_locales.py`.
- Small server changes: run Ruff on touched server files, `PYTHONPATH=server python server/manage.py check`, and focused Django tests.
- Site changes: run `cd site && npm run typecheck` and `cd site && npm run build`.
- Model or migration changes: add/commit migrations, run `PYTHONPATH=server python server/manage.py makemigrations --check`, `PYTHONPATH=server python server/manage.py migrate`, and focused tests.
- Parser changes: run `PYTHONPATH=server:. .venv/bin/pytest parsers/uzum_market/test_normalizer.py`; avoid live crawls unless explicitly requested.
- Cross-cutting changes: run `.venv/bin/ruff check .` and `PYTHONPATH=server:. .venv/bin/pytest`.

## Do Not

- Do not read, print, commit, or summarize real `.env` values. Use `.env.example` for docs.
- Do not commit `.parser_state/`, `server/db.sqlite3`, `__pycache__/`, `.ruff_cache/`, `.pytest_cache/`, venvs, logs, or local browser profiles.
- Do not use `docker compose down -v` unless the user explicitly asks; it removes the PostgreSQL `pgdata` volume.
- Do not add dependencies casually. Update `pyproject.toml` and/or `server/requirements.txt` intentionally and document why.
- Do not put `NEXT_PUBLIC_` on internal API keys; analytics site calls the Django API from server runtime only.
- Do not create data migrations or destructive cleanup scripts without clear confirmation.
- Do not bypass captcha, private/account pages, carts, payment flows, or anti-abuse protections.

## Definition of Done

Before reporting completion:

- The requested change is implemented in the correct service boundary.
- Relevant docs, env examples, migrations, and tests are updated together.
- Scoped verification has been run, or skipped with a concrete reason.
- `git status --short` has been checked.
- User-facing behavior, operational impact, and any remaining risks are summarized clearly.

## Deeper Agent Docs

- `docs/agents/project-overview.md`
- `docs/agents/architecture.md`
- `docs/agents/dev-workflow.md`
- `docs/agents/testing-and-verification.md`
- `docs/agents/feature-workflow.md`
- `docs/agents/code-style-and-conventions.md`
- `docs/agents/backend-guidelines.md`
- `docs/agents/api-contracts.md`
- `docs/agents/database-and-migrations.md`
- `docs/agents/deployment-and-env.md`
- `docs/agents/code-review.md`
- `docs/agents/common-pitfalls.md`
- `docs/agents/plans-template.md`
