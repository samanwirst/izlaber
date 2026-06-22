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
- Rebuild indexes after large imports or search-field changes.

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

