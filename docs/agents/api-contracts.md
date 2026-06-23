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
| `GET /api/v1/user-consents/` | Load Telegram consent records. Bot preload uses `active_only=true&version=...`. |
| `GET/POST /api/v1/user-consents/{telegram_user_id}/` | Read one consent record or record `accept`, `decline`, or `revoke`. |
| `POST /api/v1/analytics/events/` | Store bot-side analytics events. |
| `GET /api/v1/analytics/summary/` | Aggregated analytics dashboard data for the Next.js analytics site. Supports `days` up to 180 and returns `period`, `kpis`, `time_series`, `event_mix`, `top_queries`, `top_products`, `languages`, `input_types`, and `consents`. |
| `GET/POST /api/v1/sponsored-campaigns/` | List or create sponsored bot product campaigns for the analytics dashboard. |
| `GET/PATCH /api/v1/sponsored-campaigns/{id}/` | Read or update one sponsored campaign, including status changes. |
| `GET /api/v1/sponsored-placements/` | Return active, capped, keyword-matched sponsored product cards for the bot. Supports `q`, `language_code`, and `limit`. |
| `GET /api/v1/redirect/products/{product_id}/` | Store product click analytics, optionally set analytics cookie, then redirect to product URL. |

Bot client wrapper: `bot/services/api_client.py`.

Consent contract:

- `action=accept` sets both personal data and sponsored ads timestamps and clears `revoked_at`/`declined_at`.
- `action=decline` clears acceptance timestamps and stores `declined_at`.
- `action=revoke` stores `revoked_at`; the bot must treat the user as inactive until they accept again.
- `has_active_consent` is true only when the stored version matches the requested/current version and both acceptance timestamps exist.

Sponsored campaign contract:

- Campaign creation requires `name`, `advertiser_name`, `keywords`, and either `product_id`
  or `product_lookup` (internal ID, source product ID, or product URL).
- Bot placement responses reuse compact product card fields and add `is_sponsored`,
  `sponsored_campaign_id`, `sponsored_campaign_name`, and
  `sponsored_advertiser_name`.
- Sponsored impressions use `sponsored_impression`; sponsored redirect clicks use
  `sponsored_click`. Keep them separate from organic metrics.

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
