# Architecture

## Service Boundaries

| Service | Can import | Must not import | External interface |
| --- | --- | --- | --- |
| `bot/` | Bot modules, shared installed dependencies | Django apps, parser modules, direct DB code | Server API via `ServerAPIClient`. |
| `server/` | Django apps under `server/apps/` | Bot handlers/services, parser runtime | DRF endpoints under `/api/v1/` and `/api/internal/`. |
| `site/` | Next.js App Router files under `site/app/`, server utilities under `site/lib/` | Bot code, parser code, direct DB code, browser-exposed internal keys | Server-side calls to `/api/v1/analytics/summary/`. |
| `parsers/` | Parser modules, shared installed dependencies | Django models, bot code | Server internal API via parser storage client. |

## Server Apps

| App | Responsibility |
| --- | --- |
| `apps.api_auth` | Internal API key authentication classes. |
| `apps.catalog` | Marketplace/category/product models, search, visual search/index, bot-facing read API, user preferences. |
| `apps.crawling` | Parser-facing ingestion API, crawl run lifecycle, product upsert, deactivation logic. |

## Bot Structure

| Path | Responsibility |
| --- | --- |
| `bot/main.py` | Load config, create bot/dispatcher, preload language prefs, start polling, start AI monitor. |
| `bot/loader.py` | Bot and dispatcher construction. |
| `bot/handlers/common.py` | Main search, photo, voice, guest query, pagination flows. |
| `bot/handlers/admin.py` | Admin-only operational commands such as `/balance`. |
| `bot/handlers/language.py` | `/lang` and user language persistence. |
| `bot/services/api_client.py` | Typed-ish server API wrapper and product rendering helpers. |
| `bot/services/ai_*` | AI search/rerank/photo/voice/runtime behavior. |

## Parser Structure

| Path | Responsibility |
| --- | --- |
| `cli.py` | Parser command-line entrypoint. |
| `config.py` | Parser env config. |
| `browser.py` | Chrome/CDP browser session and category/card extraction. |
| `normalizer.py` | Converts raw site data into server product payloads. |
| `pipeline.py` | Crawl orchestration, delta checks, batch writes. |
| `storage.py` | Server API writes and local checkpoint store. |

## Analytics Site Structure

| Path | Responsibility |
| --- | --- |
| `site/app/page.tsx` | Dynamic dashboard route; fetches summary server-side. |
| `site/app/components/AnalyticsDashboard.tsx` | Client-only chart rendering from already aggregated data. |
| `site/lib/api.ts` | Internal server API fetch with `ANALYTICS_API_KEY` or `BOT_API_KEY`. |
| `site/lib/types.ts` | TypeScript contract for `/api/v1/analytics/summary/`. |

## Search Architecture

- PostgreSQL path uses `Product.search_text`, GIN/trigram behavior, price filters, and fallback relaxation.
- SQLite path uses `ProductSearchTerm` rows as the fallback token index.
- Bot-side AI rerank is optional and should operate on a bounded candidate set from the server.
- Photo search combines exact/near cover fingerprint matching with optional visual rerank.

## State Rules

- Persist durable user preferences in server DB, not local bot files.
- Keep parser checkpoints under `.parser_state/`.
- Avoid adding cross-service shared state unless the server owns it.
