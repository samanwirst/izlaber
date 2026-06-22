# Project Overview

## What This Project Is

Izlaber is a Telegram product search bot backed by a normalized marketplace catalog.

Users can search by text, photo, or voice. The bot returns product cards with cover images, prices, ratings, and links. A parser pipeline refreshes marketplace catalog data and sends normalized products to the Django API.

## Major Domains

| Domain | Owner paths | Notes |
| --- | --- | --- |
| Telegram bot UX | `bot/handlers/`, `bot/keyboards/`, `bot/locales.py` | aiogram handlers, localized copy, reply/inline keyboards. |
| Bot service layer | `bot/services/` | Server API client, AI rerank/vision/audio, runtime monitor, search state. |
| Catalog API | `server/apps/catalog/` | Product search, visual search, user language preferences, serializers. |
| Crawl ingestion API | `server/apps/crawling/` | Crawl runs, batch upsert, product hash lookup, seen product tracking. |
| Analytics dashboard | `site/` | Next.js dashboard for aggregated bot/search/product analytics. |
| Parser pipeline | `parsers/uzum_market/` | Chrome/CDP and GraphQL-based crawler with checkpoint state. |
| Operations | `scripts/`, `docker-compose.yml`, Dockerfiles | Local Docker, parser wrappers, audits, index rebuilds. |

## Current Data Flow

1. Parser discovers category/product cards.
2. Parser normalizes cards and computes `content_hash`.
3. Parser sends batches to `/api/internal/products/upsert-batch/`.
4. Server upserts `Product`, updates search fields, tracks crawl run stats.
5. Bot queries `/api/v1/products/` through `ServerAPIClient`.
6. Bot optionally reranks or expands results with AI, then sends Telegram cards.
7. Analytics site reads `/api/v1/analytics/summary/` server-side and renders charts.

## Important Runtime Data

| Data | Location | Persistence |
| --- | --- | --- |
| Products and crawl runs | PostgreSQL or local SQLite | Database-backed. |
| User language preferences | `catalog_userpreference` | Database-backed. |
| Analytics events | `catalog_analyticsevent` | Database-backed bot/search/click events. |
| Analytics dashboard cache/build output | `site/.next/`, `site/node_modules/` | Ignored local build/runtime data. |
| Bot pagination state | `bot/services/search_state.py` memory | Lost on bot restart. |
| Parser checkpoint/browser profile | `.parser_state/uzum_market/` | Local ignored runtime data. |
| Cover visual fingerprints | `Product.cover_image_ahash/dhash` | Database-backed; refresh with visual index script. |

## Needs Confirmation

- There is no CI workflow in `.github/` at the time of inspection.
- No dedicated typecheck command is configured.
- No documented repo-wide formatter command exists beyond Ruff availability.
