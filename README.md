# Izlaber Marketplace Aggregator

Telegram-based marketplace aggregator with separated services:

```text
bot/                 Telegram bot, talks only to DRF API
server/              Django + DRF catalog and ingestion API
site/                Next.js analytics dashboard
parsers/uzum_market/ Standalone marketplace parser pipeline
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

SQLite is used by default for direct local Python runs. For production-sized catalog data,
use PostgreSQL:

```bash
export DATABASE_URL=postgres://izlaber:izlaber@127.0.0.1:15432/izlaber
PYTHONPATH=server python server/manage.py migrate
PYTHONPATH=server python server/manage.py rebuild_product_search_index --marketplace uzum --skip-token-index
```

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

Bot profile and command descriptions are localized for Uzbek, Russian, and English.
Uzbek is the default fallback language. Apply or refresh Telegram profile text after
copy changes:

```bash
python -m bot.setup_profile
```

Bot search flow:

- Before search, the bot requires consent for personal data processing and sponsored ads. Without active consent, `/start`, text, photo, voice, guest search, callbacks, and admin commands are blocked and the bot shows a combined Uzbek/Russian/English consent prompt with one reply keyboard acceptance button. Policy URLs are shown as text links in the prompt.
- Consent decisions are stored in the server database as `UserConsent` records. `BOT_CONSENT_VERSION` and `USER_CONSENT_VERSION` must match; bump the version whenever the consent text or covered data uses materially change.
- Public policy pages are served by Django at `/legal/privacy/` and `/legal/sponsored-ads/`. If `BOT_PRIVACY_POLICY_URL` or `BOT_SPONSORED_ADS_POLICY_URL` are empty, the bot derives them from `BOT_PUBLIC_BASE_URL`.
- Users can review consent with `/consent` and revoke it with `/consent revoke`. Users without active consent can accept again from the same one-button prompt.
- Implementation notes and legal-source links are in `docs/consent.md`.
- User sends a product name.
- User can also send a product photo; the bot uses a visual matching pipeline to find similar product cards.
- Bot detects the user's Telegram app language and answers in Uzbek, Russian, or English.
- Bot sends 10 product cards with cover, price, rating, and link.
- The localized `Yana` / `Еще` / `More` keyboard button sends the next 10 cards for the latest query of that exact chat/user.
- Any new product text resets that user's search offset, so old searches are not mixed.
- Bot-side rate limiting is enabled by default. `BOT_RATE_LIMIT_MAX_EVENTS` caps all
  interactions, `BOT_SEARCH_RATE_LIMIT_MAX_EVENTS` caps text/photo/voice/More searches,
  and `BOT_AI_RATE_LIMIT_MAX_EVENTS` caps photo/voice requests that can spend AI tokens.
  `OPENAI_STATUS_NOTIFY_USER_ID` bypasses these limits by default for admin checks.

Analytics:

- Bot actions are stored in `catalog_analyticsevent`: `/start`, `/help`, `/lang`, text/photo/voice searches, no-result searches, `More`, product impressions, and product clicks.
- Search and impression events follow marketplace-friendly event names where practical: `search`, `view_item_list`, and `select_item`.
- The analytics dashboard lives in `site/` and reads aggregated data from `GET /api/v1/analytics/summary/` using `ANALYTICS_API_KEY` or `BOT_API_KEY`.
- Product click tracking uses `/api/v1/redirect/products/{id}/` and then redirects to the real product URL. Set `BOT_PUBLIC_BASE_URL` to the public server origin so Telegram users can open those tracking links.
- Cookie-level click attribution is off by default. Enable `ANALYTICS_COOKIE_ENABLED=true` only when the active consent text and privacy policy cover analytics cookies.
- Raw IP addresses are not stored. Optional IP hashing is controlled by `ANALYTICS_HASH_IP`.

Run analytics site locally:

```bash
cd site
npm install
npm run dev
```

Docker exposes the analytics site on `SITE_PORT` (`3000` by default):

```bash
docker compose up --build server site
```

Guest Mode:

- If Telegram Guest Mode is enabled for the bot in BotFather, users can mention the bot from chats where it is not a member.
- Guest requests return one compact top-5 result via `answerGuestQuery`; they do not reuse or mutate the private-chat `Еще` pagination state.
- Set `BOT_GUEST_SEARCH_ENABLED=false` to disable this handler locally.

Product search uses PostgreSQL FTS/trigram indexes when `DATABASE_URL` points to
PostgreSQL, and falls back to the token index on SQLite. Rebuild the local search
data after large manual DB imports:

```bash
./scripts/rebuild_product_search_index.sh --marketplace uzum
```

Optional rerank:

- Set `OPENAI_API_KEY` in `.env` to enable reranking.
- By default `OPENAI_RERANK_FALLBACK_ONLY=true`: the bot first returns fast PostgreSQL results and calls OpenAI only when the local top results look weak.
- Photo search uses a visual matching pipeline: the bot understands the user photo, fetches a small candidate set from PostgreSQL, then visually reranks candidate cover images. This avoids returning every generic mug or cream.
- Voice messages are transcribed to text, then passed through the same product search pipeline.
- `OPENAI_PHOTO_VISUAL_RERANK_LIMIT` controls how many candidate covers are sent to the model. Keep it around `12-16` for a good cost/quality balance.
- `OPENAI_VOICE_MODEL=gpt-4o-mini-transcribe` is the cheapest practical option for Telegram voice notes in the current stack.
- `PHOTO_VISUAL_MATCH_ENABLED=true` is still useful as a cheap exact-cover fallback when the model is unavailable.
- Build or refresh cover fingerprints after migration or large imports with `./scripts/rebuild_product_visual_index.sh --marketplace uzum`. Exact cover matching can only match products whose covers are indexed.
- For a targeted repair/check use `./scripts/rebuild_product_visual_index.sh --marketplace uzum --source-product-id 2797446`.
- `OPENAI_PHOTO_TEXT_FALLBACK_ENABLED=false` by default, so weak text-only photo matches are not sent when visual rerank finds no close match.
- Tune exact photo matching with `PHOTO_VISUAL_MATCH_MAX_DISTANCE`; lower values are stricter.
- If fallback-only mode is disabled, the bot fetches `OPENAI_RERANK_CANDIDATE_LIMIT` indexed candidates, then asks the configured OpenAI model to reorder only those candidates.
- If the indexed candidates look irrelevant or too sparse, the model can generate up to `OPENAI_SEARCH_EXPAND_MAX_QUERIES` extra search queries with optional price filters, then the bot fetches more candidates and reranks the merged pool.
- If OpenAI returns quota/billing exhaustion, the bot notifies `OPENAI_STATUS_NOTIFY_USER_ID`, switches to local-only search, probes OpenAI every `OPENAI_BALANCE_PROBE_INTERVAL` seconds, and reenables the advanced path automatically when the API is available again.
- `/balance` is available only to `OPENAI_STATUS_NOTIFY_USER_ID`. It shows live availability; with `OPENAI_ADMIN_API_KEY` it also shows official Costs API spend, and with `OPENAI_MONTHLY_BUDGET_USD` it estimates remaining configured budget.
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

Audit existing catalog data:

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
docker compose up --build server bot site
```

Docker starts PostgreSQL by default and points the API at
`postgres://izlaber:izlaber@postgres:5432/izlaber`. The SQLite database, parser
state, virtualenvs, and caches are excluded from Docker build context by
`.dockerignore`, so image builds do not upload local data.
The API is exposed on host port `8001` by default; override with `SERVER_PORT`.
PostgreSQL is exposed on host port `15432` by default; override with `POSTGRES_PORT`.
The analytics site is exposed on host port `3000` by default; override with `SITE_PORT`.
`docker compose down` keeps named volumes such as `pgdata`; only
`docker compose down -v` removes them.

One-time migration from the current SQLite catalog to Docker PostgreSQL:

```bash
docker compose up -d postgres
docker compose run --rm server python manage.py migrate
docker compose run --rm server python manage.py copy_sqlite_to_postgres --truncate
docker compose run --rm server python manage.py rebuild_product_search_index --marketplace uzum --skip-token-index
```

`copy_sqlite_to_postgres` skips `catalog_productsearchterm` by default because the
PostgreSQL search path uses `Product.search_text` with GIN indexes, and the token
index is only needed for the SQLite fallback.

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

## Tests

```bash
PYTHONPATH=server:. pytest
```

## Limitations

The parser uses a local Chrome profile to seed its own persistent runtime browser profile, crawls category listing pages plus their pagination, and can wait for a manual SmartCaptcha solve in `--headful` mode. It does not bypass private/account pages, carts, payments, or protections automatically.
