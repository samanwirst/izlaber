# parsers/AGENTS.md

Rules for parser work:

- Parsers are standalone ingestion clients; they write through `server/apps/crawling/` API only.
- Keep crawler state in `.parser_state/`; it is local runtime data and must stay ignored.
- Preserve delta-crawl behavior: unchanged products are skipped by `content_hash`, full runs record seen products, and only successful unlimited full runs should deactivate unseen products.
- Do not bypass captcha, account-only areas, carts, payments, or anti-abuse protections.
- Live crawls can be slow and stateful. Prefer unit tests and dry-run/test mode unless the user asks for a real crawl.

Useful focused checks:

```bash
PYTHONPATH=server:. .venv/bin/pytest parsers/uzum_market/test_normalizer.py
python -m parsers.uzum_market.cli crawl --mode test --limit 10 --dry-run
```

