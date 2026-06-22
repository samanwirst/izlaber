# Izlaber Marketplace Aggregator

Telegram-based marketplace aggregator with separated services:

```text
bot/                 Telegram bot, talks only to DRF API
server/              Django + DRF catalog and ingestion API
parsers/uzum_market/ Standalone Uzum Market parser pipeline
```

The bot never imports parser code and never reads the database directly. Parsers send normalized products to `server` through internal ingestion endpoints using `PARSER_API_KEY`. The bot searches products through read endpoints using `BOT_API_KEY`.

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Fill `TELEGRAM_BOT_TOKEN`, `BOT_API_KEY`, and `PARSER_API_KEY` in `.env`.

## Run Server

```bash
PYTHONPATH=server python server/manage.py migrate
PYTHONPATH=server python server/manage.py createsuperuser
PYTHONPATH=server python server/manage.py runserver 0.0.0.0:8000
```

SQLite is used by default. For PostgreSQL set `DATABASE_URL`.

## Run Bot

```bash
source .venv/bin/activate
python -m bot
```

Direct script launch is also supported:

```bash
python bot/main.py
cd bot && ../.venv/bin/python main.py
```

Bot search flow:

- User sends a product name.
- Bot sends 5 Uzum cards with cover, price, rating, and link.
- The `Еще` keyboard button sends the next 5 cards for the latest query of that exact chat/user.
- Any new product text resets that user's search offset, so old searches are not mixed.

Guest Mode:

- If Telegram Guest Mode is enabled for the bot in BotFather, users can mention the bot from chats where it is not a member.
- Guest requests return one compact top-5 Uzum result via `answerGuestQuery`; they do not reuse or mutate the private-chat `Еще` pagination state.
- Set `BOT_GUEST_SEARCH_ENABLED=false` to disable this handler locally.

Product search uses a token index. Rebuild it after large manual DB imports:

```bash
./scripts/rebuild_product_search_index.sh --marketplace uzum
```

Optional AI rerank:

- Set `OPENAI_API_KEY` in `.env` to enable neural reranking.
- The bot first fetches `OPENAI_RERANK_CANDIDATE_LIMIT` indexed candidates, then asks the configured OpenAI model to reorder only those candidates.
- If the indexed candidates look irrelevant or too sparse, the model can generate up to `OPENAI_SEARCH_EXPAND_MAX_QUERIES` extra search queries with optional price filters, then the bot fetches more candidates and reranks the merged pool.
- If OpenAI returns quota/billing exhaustion, the bot notifies `OPENAI_STATUS_NOTIFY_USER_ID`, switches to local-only search, probes OpenAI every `OPENAI_BALANCE_PROBE_INTERVAL` seconds, and enables AI automatically when the API is available again.
- `/balance` is available only to `OPENAI_STATUS_NOTIFY_USER_ID`. It shows live AI availability; with `OPENAI_ADMIN_API_KEY` it also shows official Costs API spend, and with `OPENAI_MONTHLY_BUDGET_USD` it estimates remaining configured budget.
- Default model is `gpt-5.4-nano` for low cost.
- If OpenAI is unavailable or the key is missing, the bot falls back to indexed search order.

## Run Parser

One-command full crawl:

```bash
./scripts/run_uzum_full.sh
```

The wrapper performs a fresh full catalog scan, but writes only new/changed cards to
the database. Unchanged products are skipped by `content_hash`, deleted products are
deactivated only after a successful unlimited full run, and `audit_uzum_catalog` runs
automatically at the end.

If the wrapper says `Server API is not reachable`, start Django first:

```bash
PYTHONPATH=server python server/manage.py runserver 0.0.0.0:8000
```

Test mode:

```bash
python -m parsers.uzum_market.cli crawl --mode test --limit 100
```

Full crawl:

```bash
python -m parsers.uzum_market.cli crawl --mode full
```

Visible browser mode for captcha/manual verification:

```bash
python -m parsers.uzum_market.cli crawl --mode full --headful
```

Resume:

```bash
python -m parsers.uzum_market.cli crawl --mode full --resume
```

Audit existing Uzum data:

```bash
./scripts/audit_uzum_catalog.sh --require-checkpoint
```

Dry run:

```bash
python -m parsers.uzum_market.cli crawl --mode test --limit 10 --dry-run
```

## Docker

Fast local launch for the API and bot:

```bash
./scripts/docker-start.sh
```

Equivalent raw Docker command:

```bash
docker compose up --build server bot
```

The server uses the existing `./server/db.sqlite3` through a bind mount, so the
current parsed catalog is available inside Docker. The SQLite database, parser
state, virtualenvs, and caches are excluded from Docker build context by
`.dockerignore`, so image builds do not upload local data.

Useful Docker commands:

```bash
docker compose logs -f bot
docker compose logs -f server
docker compose down
docker compose run --rm server python manage.py rebuild_product_search_index --marketplace uzum
```

Parser:

```bash
docker compose --profile parser run --rm parser python -m parsers.uzum_market.cli crawl --mode test --limit 100
docker compose --profile parser run --rm parser python -m parsers.uzum_market.cli crawl --mode full --resume
```

PostgreSQL profile:

```bash
DATABASE_URL=postgres://izlaber:izlaber@postgres:5432/izlaber docker compose --profile postgres up --build
```

## Tests

```bash
PYTHONPATH=server:. pytest
```

## Limitations

The Uzum parser uses a local Chrome profile to seed its own persistent runtime browser profile, crawls category listing pages plus their pagination, and can wait for a manual SmartCaptcha solve in `--headful` mode. It does not bypass private/account pages, carts, payments, or protections automatically.
