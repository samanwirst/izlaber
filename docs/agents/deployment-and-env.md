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

## Docker Compose

Services:

| Service | Purpose |
| --- | --- |
| `postgres` | PostgreSQL 16 with `pgdata` named volume. |
| `server` | Django API, runs migrations before runserver. |
| `bot` | Telegram bot polling process. |
| `parser` | Optional parser profile service. |

Commands:

```bash
docker compose up --build server bot
docker compose logs -f server
docker compose logs -f bot
docker compose --profile parser run --rm parser python -m parsers.uzum_market.cli crawl --mode test --limit 100
docker compose down
```

## Ports

| Variable | Default | Purpose |
| --- | --- | --- |
| `SERVER_PORT` | `8001` | Host port for Django API in Docker. |
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

