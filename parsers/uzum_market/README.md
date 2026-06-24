# Uzum Market Parser

Standalone parser for Uzum Market catalog/product data.

The parser now uses a real local Chrome profile through direct Chrome DevTools Protocol control. This makes it possible to crawl the catalog through a normal browser session, reusing your existing cookies/profile state instead of relying on brittle raw HTTP requests that hit SmartCaptcha immediately.

## Commands

```bash
./scripts/run_uzum_full.sh
./scripts/collect_uzum_category_coverage.sh
PYTHONPATH=server python server/manage.py audit_uzum_category_coverage .parser_state/uzum_market/category-coverage.json
PYTHONPATH=server python server/manage.py audit_uzum_category_coverage .parser_state/uzum_market/category-coverage.json --write-parser-shards .parser_state/uzum_market/shards --shards 6 --exclude-processed-state .parser_state/uzum_market
./scripts/backfill_uzum_search.sh snickers "шоколадный батончик"
./scripts/audit_uzum_catalog.sh --require-checkpoint
UZUM_LIMIT=100 UZUM_DRY_RUN=true ./scripts/run_uzum_full.sh
UZUM_DISCOVERY_START_URLS=https://uzum.uz/ru/category/elektronika-10020 ./scripts/run_uzum_full.sh
python -m parsers.uzum_market.cli crawl --mode test --limit 100
python -m parsers.uzum_market.cli crawl --mode incremental
python -m parsers.uzum_market.cli crawl --mode full
python -m parsers.uzum_market.cli crawl --mode full --resume
python -m parsers.uzum_market.cli crawl --mode full --headful
python -m parsers.uzum_market.cli crawl --mode full --dry-run
python -m parsers.uzum_market.cli backfill-search snickers --limit 100 --headful
python -m parsers.uzum_market.cli backfill-urls --headful https://uzum.uz/ru/product/batonchik-snickers-50-g-42828
python -m parsers.uzum_market.cli backfill-urls --url-file .parser_state/uzum_market/product-urls.txt --headful
```

Required env:

```bash
SERVER_API_BASE_URL=http://127.0.0.1:8000/api
PARSER_API_KEY=change-me-parser-key
UZUM_CRAWL_DELAY_SECONDS=1.5
UZUM_MAX_RETRIES=3
UZUM_BATCH_SIZE=50
UZUM_DELTA_COMPARE_BATCH_SIZE=1000
UZUM_REQUEST_TIMEOUT=20
UZUM_AUDIT_AFTER=true
UZUM_BROWSER_EXECUTABLE_PATH=/usr/bin/google-chrome-stable
UZUM_BROWSER_PROFILE_SOURCE=/home/you/.config/google-chrome
UZUM_BROWSER_PROFILE_NAME=Default
UZUM_BROWSER_RUNTIME_PROFILE_DIR=.parser_state/uzum_market/browser-profile
UZUM_BROWSER_HEADLESS=true
UZUM_DISCOVERY_START_URLS=https://uzum.uz/ru/category/vse-kategorii-1
UZUM_AUTH_TOKEN=
UZUM_X_IID=
```

Notes:

- The main repeatable entrypoint is `./scripts/run_uzum_full.sh`. By default it runs `full + resume + headful`, then runs `./scripts/audit_uzum_catalog.sh --require-checkpoint`.
- In non-`dry-run` mode the wrapper checks that `SERVER_API_BASE_URL` is reachable before starting the browser. If not, start Django first.
- `--headful` launches visible Chrome and waits up to `UZUM_BROWSER_CAPTCHA_TIMEOUT_SECONDS` for you to solve SmartCaptcha manually if Uzum shows it.
- The parser initializes its own runtime Chrome profile in `UZUM_BROWSER_RUNTIME_PROFILE_DIR`. On the first run it seeds that profile from your local Chrome profile; later runs reuse the saved browser state, which helps preserve cookies and any anti-bot/session state across launches.
- In Docker, `Dockerfile.parser` installs Chromium and defaults to an empty seed profile under `.parser_state` if no local Chrome profile is available. If Uzum shows SmartCaptcha in headless mode, run with a prepared browser profile or use a headful environment to solve it once.
- If `UZUM_AUTH_TOKEN` is set, the parser uses direct REST/GraphQL mode and does not launch Chrome. The token is the short-lived `auth_sdk_access_token` from an authorized Uzum web session; refresh it before long server runs. `UZUM_X_IID` is optional, but can be set from the same web session.
- Discovery opens `https://uzum.uz/ru/category/vse-kategorii-1`, reads the real `root-categories` API response from the browser session, and synthesizes leaf category URLs from the full category tree. Leaf categories avoid repeatedly crawling parent categories that mostly aggregate duplicate child products.
- If `UZUM_DISCOVERY_START_URLS` is set to one or more concrete category URLs, discovery uses only those URLs. This is the safe path for targeted gap backfills, for example `UZUM_DISCOVERY_START_URLS=https://uzum.uz/ru/category/batonchiki-369 ./scripts/run_uzum_full.sh`.
- Product crawling uses the site's `MakeSearch_ItemsAndFilters` GraphQL operation. With `UZUM_AUTH_TOKEN` it uses a built-in query directly; otherwise it captures the query and required headers from the live browser session. The crawler requests category cards in API batches of 100 by `categoryId + offset`, so it does not render every category page or scroll the DOM during the main crawl. DOM extraction remains as a fallback for URLs that cannot be served through GraphQL.
- Large categories are split by price before offsets exceed about 5,000 items. This avoids unstable high-offset GraphQL pages that can return `search_phase_execution_exception`.
- `./scripts/collect_uzum_category_coverage.sh` collects live GraphQL totals per category into `.parser_state/uzum_market/category-coverage.json`. Compare it with the database via `python server/manage.py audit_uzum_category_coverage ...` to find the largest concrete gaps before launching targeted backfills.
- Coverage `gap_total` is a category-total delta, not a guaranteed missing unique-product count. Uzum can return the same product through multiple categories or search segments, while Izlaber stores one `Category` FK per product. Treat large gaps as crawl targets to validate, then judge the result by `created_count`, active product growth, and focused category/brand checks.
- `audit_uzum_category_coverage --write-parser-shards <dir> --shards N` writes `shardXX.env` files with weighted `UZUM_DISCOVERY_START_URLS` lists for targeted incremental Docker backfills. Use `--exclude-processed-state` with a checkpoint file or state directory to avoid categories already completed by earlier shard runs.
- `./scripts/backfill_uzum_search.sh <query...>` uses the same captured GraphQL operation with `text` search input. Use it for targeted catalog gaps found by bot/photo analytics, for example a brand or product type that is missing from the local database. It writes only new/changed cards through the ingestion API and never deactivates unseen products.
- `python -m parsers.uzum_market.cli backfill-urls <url...>` is for product or SEO/listing URLs that exist on the site but are not reachable through numeric category GraphQL crawling. Product URLs are parsed from the live product page JSON-LD; listing URLs first collect product links and then parse detail pages. Use `--url-file` for one URL per line. This path still writes through the ingestion API and never deactivates unseen products.
- Full runs are delta-updated. The parser still scans listing cards to detect new, changed, and deleted products, but before writing products it asks the server for existing `source_product_id -> content_hash` values. Unchanged cards are skipped and do not rewrite `Product` rows. The server records `seen_products` for the crawl run and deactivates only active products not seen in a successful unlimited full run.
- A completed checkpoint is treated as historical state. Re-running `./scripts/run_uzum_full.sh` starts a fresh delta scan instead of skipping all categories from the previous successful run. If a run crashes before completion, the same command resumes from the unfinished checkpoint.
- `UZUM_LIMIT` is safe for tests: limited runs do not deactivate unseen products.
- `UZUM_DISCOVERY_START_URLS` accepts a comma-separated list of category URLs. It is useful for targeted retries or partial re-crawls without changing code.
- Card links are stored in `Product.canonical_url`. Card covers are stored explicitly in `Product.cover_image_url` and are derived from the first high-quality GraphQL card image, normally `t_product_540_high`.
- `./scripts/audit_uzum_catalog.sh --require-checkpoint` verifies product count, active coverage, canonical links, cover images, latest crawl status, failed/blocked checkpoint URLs, and exits with code 1 on critical failures.
- Practical workflow:
  1. Run `./scripts/run_uzum_full.sh`
  2. If SmartCaptcha appears, solve it once in the opened Chrome window
  3. Re-run the same command later; it will reuse the saved runtime profile and perform a fresh delta scan
