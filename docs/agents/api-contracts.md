# API Contracts

## Public Internal API Prefixes

| Prefix | Consumer | Auth |
| --- | --- | --- |
| `/api/v1/` | Telegram bot and internal tools | `BOT_API_KEY` |
| `/api/internal/` | Parser ingestion pipeline | `PARSER_API_KEY` |
| `/api/schema/`, `/api/docs/` | API schema/docs | Django/DRF config |

All internal consumers use `X-Internal-API-Key`.

## Bot-Facing Endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /api/v1/products/` | Search/list product cards. Supports `q`, `marketplace`, `limit`, `offset`, `active_only`, price filters, category. |
| `GET /api/v1/products/{id}/` | Product detail. |
| `POST /api/v1/products/visual-search/` | Search by cover image fingerprints. |
| `POST /api/v1/products/visual-index/` | Build/refresh cover fingerprints for selected products. |
| `GET /api/v1/marketplaces/` | Active marketplaces. |
| `GET /api/v1/categories/` | Categories, optionally by marketplace. |
| `GET /api/v1/user-preferences/languages/` | Load all stored Telegram language preferences. |
| `GET/POST /api/v1/user-preferences/languages/{telegram_user_id}/` | Read/write one language preference. |

Bot client wrapper: `bot/services/api_client.py`.

## Parser-Facing Endpoints

| Endpoint | Purpose |
| --- | --- |
| `POST /api/internal/crawl-runs/start/` | Create running crawl run. |
| `POST /api/internal/products/hash-batch/` | Fetch existing product hash/active states for delta crawl. |
| `POST /api/internal/products/upsert-batch/` | Upsert normalized product batches. |
| `POST /api/internal/crawl-runs/{id}/seen-products/` | Record products seen during a crawl. |
| `POST /api/internal/crawl-runs/{id}/finish/` | Finish crawl, optionally deactivate unseen products. |
| `POST /api/internal/crawl-events/` | Record parser events. |

Parser client/storage code: `parsers/uzum_market/storage.py`.

## Contract Change Checklist

- Update serializers, views, and URLs together.
- Update `bot/services/api_client.py` or parser storage client if response/request shape changes.
- Add or update tests covering status code, auth, and response keys.
- Update `server/README.md` and agent docs when a new endpoint is durable.
- Keep response payloads bounded; avoid returning full raw product data from list endpoints.

