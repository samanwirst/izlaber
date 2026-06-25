# Deployment And Environment

## Environment Files

- Use `.env.example` as the documented source of variable names.
- Do not read or print real `.env` values in final answers.
- `.env` and `.env.*` are ignored; `.env.example` is allowed.

## Required Local Values

Minimum useful local setup:

```text
TELEGRAM_BOT_TOKEN
BOT_API_KEY
PARSER_API_KEY
SERVER_API_BASE_URL
```

Optional AI/photo/voice behavior is controlled by `OPENAI_*` and `PHOTO_VISUAL_*` variables.

Analytics site variables:

| Variable | Purpose |
| --- | --- |
| `SITE_PORT` | Host port for the Next.js analytics site in Docker Compose. |
| `ANALYTICS_API_KEY` | Optional dedicated internal API key for the analytics site. Falls back to `BOT_API_KEY` if empty. |
| `SITE_ADMIN_USERNAME` | Analytics login username. Defaults to `admin`. |
| `SITE_ADMIN_PASSWORD` | Analytics login password. Defaults to `admin`; change in production when practical. |
| `SITE_ADMIN_TELEGRAM_IDS` | Comma-separated Telegram admin IDs that receive 8-symbol login codes. |
| `SITE_AUTH_SECRET` | Secret for signed dashboard session/code cookies. Use a random production value. |
| `SITE_AUTH_SESSION_TTL_SECONDS` | Analytics session lifetime. Defaults to 12 hours. |
| `SITE_AUTH_CODE_TTL_SECONDS` | Telegram login code lifetime. Defaults to 10 minutes. |

The analytics site must keep auth server-side. Do not expose `ANALYTICS_API_KEY`,
`BOT_API_KEY`, `TELEGRAM_BOT_TOKEN`, or auth secrets to browser components.

Consent variables:

| Variable | Purpose |
| --- | --- |
| `BOT_CONSENT_ENABLED` | Enables bot-side consent gate. Keep enabled in production. |
| `BOT_CONSENT_VERSION` | Version string stored for new Telegram user consent. |
| `USER_CONSENT_VERSION` | Server fallback/current version; keep equal to `BOT_CONSENT_VERSION`. |
| `BOT_PRIVACY_POLICY_URL` | Optional consent prompt URL. Empty value derives from `BOT_PUBLIC_BASE_URL/legal/privacy/`. |
| `BOT_SPONSORED_ADS_POLICY_URL` | Optional consent prompt URL. Empty value derives from `BOT_PUBLIC_BASE_URL/legal/sponsored-ads/`. |

Public legal pages are served by Django at `/legal/privacy/` and `/legal/sponsored-ads/`.

Analytics variables:

| Variable | Purpose |
| --- | --- |
| `BOT_ANALYTICS_ENABLED` | Enables bot-side event writes to the server. |
| `BOT_ANALYTICS_TIMEOUT` | Short timeout for analytics writes so user search is not blocked. |
| `BOT_PUBLIC_BASE_URL` | Public server origin used to generate product click redirect links. |
| `BOT_SPONSORED_SEARCH_LIMIT` | Sponsored product cards per first search page. Set `0` to disable sponsored placements. |
| `BOT_SEARCH_TIMEOUT_SECONDS` | Overall per-search user-facing timeout. Values below `60` are raised to `60`; private-chat searches send progress pings after 5 seconds and then every 10 seconds. |
| `BOT_SEARCH_AI_RESCUE_AFTER_SECONDS` | Starts an AI query rescue inside the overall search timeout. Default `30`; set `0` to disable. |
| `BOT_MARKETPLACE_CUSTOM_EMOJI_UZUM`, `BOT_MARKETPLACE_CUSTOM_EMOJI_WILDBERRIES` | Optional Telegram custom emoji IDs for marketplace logo prefixes in product card titles. Leave empty until real IDs are available. |
| `ANALYTICS_COOKIE_ENABLED` | Enables first-party click attribution cookie on redirect endpoint. |
| `ANALYTICS_COOKIE_NAME` | Cookie name, default `izlaber_cid`. |
| `ANALYTICS_HASH_IP` | Stores salted IP hashes for redirect events when enabled. |

Bot abuse-control variables:

| Variable | Purpose |
| --- | --- |
| `BOT_RATE_LIMIT_ENABLED` | Enables bot-side rate limiting middleware. Keep enabled in production. |
| `BOT_RATE_LIMIT_MAX_EVENTS` | Sliding-window cap for all user interactions. |
| `BOT_SEARCH_RATE_LIMIT_MAX_EVENTS` | Sliding-window cap for text/photo/voice/More search inputs. |
| `BOT_AI_RATE_LIMIT_MAX_EVENTS` | Sliding-window cap for inputs that can spend AI tokens, including text search when AI fallback is enabled. |
| `BOT_SEARCH_INFLIGHT_LIMIT_ENABLED` | Allows only one active search/photo/voice/More job per user at a time. Keep enabled in production. |

## Docker Compose

Services:

| Service | Purpose |
| --- | --- |
| `postgres` | PostgreSQL 16 with `pgdata` named volume. |
| `server` | Django API, runs migrations before runserver. |
| `bot` | Telegram bot polling process. |
| `site` | Next.js analytics dashboard. |
| `parser` | Optional parser profile service. |

Commands:

```bash
docker compose up --build server bot site
docker compose logs -f server
docker compose logs -f bot
docker compose logs -f site
docker compose --profile parser run --rm parser python -m parsers.uzum_market.cli crawl --mode test --limit 100
docker compose down
```

## Ports

| Variable | Default | Purpose |
| --- | --- | --- |
| `SERVER_PORT` | `8001` | Host port for Django API in Docker. |
| `SITE_PORT` | `3000` | Host port for the analytics site in Docker. |
| `POSTGRES_PORT` | `15432` | Host port for PostgreSQL in Docker. |

Direct local Django defaults to port `8000` when run with README commands.

## Docker Build Context

`.dockerignore` excludes local secrets, parser state, caches, virtualenvs, SQLite DBs, and build output. Keep this protection intact when adding new local runtime directories.

## Operational Commands

```bash
python -m bot.setup_profile
./scripts/run_uzum_full.sh
./scripts/audit_uzum_catalog.sh --require-checkpoint
```

`./scripts/run_uzum_full.sh` checks server reachability before non-dry runs and runs audit after successful unlimited full runs unless disabled by env.
