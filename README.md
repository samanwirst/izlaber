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
python -m bot
```

Bot search flow:

- User sends a product name.
- Bot sends 5 Uzum cards with cover, price, rating, and link.
- The `Еще` keyboard button sends the next 5 cards for the latest query of that exact chat/user.
- Any new product text resets that user's search offset, so old searches are not mixed.

Product search uses a token index. Rebuild it after large manual DB imports:

```bash
./scripts/rebuild_product_search_index.sh --marketplace uzum
```

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

```bash
docker compose up --build
```

Parser:

```bash
docker compose --profile parser run --rm parser python -m parsers.uzum_market.cli crawl --mode test --limit 100
docker compose --profile parser run --rm parser python -m parsers.uzum_market.cli crawl --mode full
```

PostgreSQL profile:

```bash
docker compose --profile postgres up --build
```

## Tests

```bash
PYTHONPATH=server:. pytest
```

## Limitations

The Uzum parser uses a local Chrome profile to seed its own persistent runtime browser profile, crawls category listing pages plus their pagination, and can wait for a manual SmartCaptcha solve in `--headful` mode. It does not bypass private/account pages, carts, payments, or protections automatically.
