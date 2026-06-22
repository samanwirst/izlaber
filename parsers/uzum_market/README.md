# Uzum Market Parser

Standalone parser for Uzum Market catalog/product data.

The parser now uses a real local Chrome profile through direct Chrome DevTools Protocol control. This makes it possible to crawl the catalog through a normal browser session, reusing your existing cookies/profile state instead of relying on brittle raw HTTP requests that hit SmartCaptcha immediately.

## Commands

```bash
./scripts/run_uzum_full.sh
./scripts/audit_uzum_catalog.sh --require-checkpoint
UZUM_LIMIT=100 UZUM_DRY_RUN=true ./scripts/run_uzum_full.sh
UZUM_DISCOVERY_START_URLS=https://uzum.uz/ru/category/elektronika-10020 ./scripts/run_uzum_full.sh
python -m parsers.uzum_market.cli crawl --mode test --limit 100
python -m parsers.uzum_market.cli crawl --mode incremental
python -m parsers.uzum_market.cli crawl --mode full
python -m parsers.uzum_market.cli crawl --mode full --resume
python -m parsers.uzum_market.cli crawl --mode full --headful
python -m parsers.uzum_market.cli crawl --mode full --dry-run
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
```

Notes:

- The main repeatable entrypoint is `./scripts/run_uzum_full.sh`. By default it runs `full + resume + headful`, then runs `./scripts/audit_uzum_catalog.sh --require-checkpoint`.
- In non-`dry-run` mode the wrapper checks that `SERVER_API_BASE_URL` is reachable before starting the browser. If not, start Django first.
- `--headful` launches visible Chrome and waits up to `UZUM_BROWSER_CAPTCHA_TIMEOUT_SECONDS` for you to solve SmartCaptcha manually if Uzum shows it.
- The parser initializes its own runtime Chrome profile in `UZUM_BROWSER_RUNTIME_PROFILE_DIR`. On the first run it seeds that profile from your local Chrome profile; later runs reuse the saved browser state, which helps preserve cookies and any anti-bot/session state across launches.
- Discovery opens `https://uzum.uz/ru/category/vse-kategorii-1`, reads the real `root-categories` API response from the browser session, and synthesizes leaf category URLs from the full category tree. Leaf categories avoid repeatedly crawling parent categories that mostly aggregate duplicate child products.
- Product crawling uses the site's `MakeSearch_ItemsAndFilters` GraphQL operation after capturing the query and required headers from the live browser session. The crawler requests category cards in API batches of 100 by `categoryId + offset`, so it does not render every category page or scroll the DOM during the main crawl. DOM extraction remains as a fallback for URLs that cannot be served through GraphQL.
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
