# Backend Guidelines

## Django App Rules

- Use `apps.catalog` for catalog-owned models and bot-facing read/search endpoints.
- Use `apps.crawling` for parser ingestion and crawl lifecycle endpoints.
- Use `apps.api_auth` for internal API key auth classes.
- Keep database writes that affect products inside service functions such as `upsert_products`.

## API Auth

| Consumer | Auth class | Header |
| --- | --- | --- |
| Bot | `BotAPIKeyAuthentication` | `X-Internal-API-Key: BOT_API_KEY` |
| Parser | `ParserAPIKeyAuthentication` | `X-Internal-API-Key: PARSER_API_KEY` |

Do not expose these endpoints without internal auth.

## Query Performance

- Product list responses intentionally use `ProductCardSerializer` and a reduced queryset.
- Preserve pagination caps in views. Current product list/visual limits are capped at 100.
- Keep search candidate sets bounded before AI reranking.
- Preserve attribute-aware search terms. Queries such as `зеленая ваза` should
  normalize color words to color attribute tokens and match product `specs`, not
  relax to ordinary non-green products while color-matching products exist.
- For unfiltered bot product search, preserve marketplace diversity: the server should
  blend top-ranked Uzum and Wildberries candidates toward a 50/50 split for each
  `balance_page_size` window, while filling shortages with real matches from the
  available marketplace.
- Keep catalog intent rules and tests together. When changing `apps.catalog.search`, update
  the query intent matrix in `server/tests/test_ingestion.py` so accessory-vs-target cases
  such as phone cases, protective glass, straps, filters, and stickers stay covered.
- Rebuild indexes after large imports or search-field changes. When
  `product_search_text` or indexed `specs` handling changes, run
  `rebuild_product_search_index --marketplace <code> --skip-token-index` for each
  PostgreSQL marketplace.

## Model Changes

When changing models:

1. Update the model.
2. Create a migration with `PYTHONPATH=server python server/manage.py makemigrations`.
3. Run `PYTHONPATH=server python server/manage.py makemigrations --check`.
4. Run `PYTHONPATH=server python server/manage.py migrate`.
5. Add/update focused tests.

## Serializers

- Keep bot card payloads compact in `ProductCardSerializer`.
- Use full serializers only for retrieve/admin-like detail flows.
- Preserve backwards-compatible response keys unless bot/client code is changed in the same patch.

## Logging And Errors

- DRF validation errors should come from serializers where practical.
- Operational failures should be logged without secrets or raw token values.
- Avoid broad exception swallowing unless there is a tested fallback path.
