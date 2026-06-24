# parsers/AGENTS.md

Rules for parser work:

- Parsers are standalone ingestion clients; they write through `server/apps/crawling/` API only.
- Keep crawler state in `.parser_state/`; it is local runtime data and must stay ignored.
- Preserve delta-crawl behavior: unchanged products are skipped by `content_hash`, full runs record seen products, and only successful unlimited full runs should deactivate unseen products.
- Uzum search misses can be queued by the bot through `/api/internal/search-backfill-requests/`; keep `python -m parsers.uzum_market.cli backfill-worker` or the `uzum-search-backfill-worker` compose service as the worker path for those requests.
- Wildberries uses public menu/catalog API under `parsers/wildberries/`; keep `WB_DESTINATION_IDS` explicit for Uzbekistan delivery context and avoid browser scraping unless the API path breaks. Default `WB_DESTINATION_IDS=495` is the current Tashkent destination from `user-geo-data.wildberries.ru/get-geo-info`; do not restore older `123585551` without rechecking live WB geo data.
- Wildberries product links must stay as bare detail URLs (`https://www.wildberries.uz/catalog/<nmId>/detail.aspx`). Do not append `targetUrl`, `size`, or other frontend query params to `canonical_url`; those params are unstable and can make valid products render as "nothing found" on WB.
- For Wildberries production fills, prefer staged crawls: first `WB_STATE_DIR=.parser_state/wildberries-wide WB_PRICE_SPLIT_ENABLED=false WB_MAX_PAGES_PER_SEGMENT=3` for broad coverage, then a slower deep-fill run with a separate `WB_STATE_DIR`, for example `.parser_state/wildberries-deep`. Keep `WB_PAGE_SIZE=100`; larger values have triggered WB `429` responses.
- Use `./scripts/backfill_wildberries_search.sh <query...>` for targeted WB gaps found from bot/photo analytics; it ingests search API results without deactivating unseen products.
- Do not bypass captcha, account-only areas, carts, payments, or anti-abuse protections.
- Live crawls can be slow and stateful. Prefer unit tests and dry-run/test mode unless the user asks for a real crawl.

Useful focused checks:

```bash
PYTHONPATH=server:. .venv/bin/pytest parsers/uzum_market/test_normalizer.py
python -m parsers.uzum_market.cli crawl --mode test --limit 10 --dry-run
PYTHONPATH=server:. .venv/bin/pytest parsers/wildberries/test_normalizer.py
python -m parsers.wildberries.cli crawl --mode test --limit 10 --dry-run
```
