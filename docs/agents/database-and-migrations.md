# Database And Migrations

## Databases

| Mode | Database |
| --- | --- |
| Direct local Python with empty `DATABASE_URL` | `server/db.sqlite3` |
| Docker Compose | PostgreSQL service, `pgdata` named volume |
| Production-sized local data | PostgreSQL via `DATABASE_URL` |

`server/db.sqlite3` is local data and ignored. Do not commit it.

## Key Models

| Model | Purpose |
| --- | --- |
| `Marketplace` | Marketplace identity and base URL. |
| `Seller` | Marketplace seller metadata. |
| `Category` | Marketplace category tree/path metadata. |
| `Product` | Current product card state, prices, cover URL, search text, visual hashes. |
| `ProductSnapshot` | Historical snapshots for changed products. |
| `ProductSearchTerm` | SQLite fallback token search index. |
| `UserPreference` | Persistent Telegram user language preferences. |
| `CrawlRun` | Parser run lifecycle and counts. |
| `CrawlEvent` | Parser events. |
| `CrawlRunSeenProduct` | Products seen in a full crawl for deactivation logic. |

## Migration Commands

```bash
PYTHONPATH=server python server/manage.py makemigrations
PYTHONPATH=server python server/manage.py makemigrations --check
PYTHONPATH=server python server/manage.py migrate
docker compose exec server python manage.py migrate
```

## Index Rebuilds

Search index:

```bash
./scripts/rebuild_product_search_index.sh --marketplace uzum
```

Visual cover fingerprint index:

```bash
./scripts/rebuild_product_visual_index.sh --marketplace uzum
./scripts/rebuild_product_visual_index.sh --marketplace uzum --source-product-id 2797446
```

Audit:

```bash
./scripts/audit_uzum_catalog.sh --require-checkpoint
```

## Data Safety Rules

- Do not use `docker compose down -v` unless the user explicitly wants to delete local PostgreSQL data.
- Limited parser runs must not deactivate unseen products.
- Only successful unlimited full runs should deactivate unseen products.
- If changing `content_hash` inputs, expect broad product updates on the next crawl; call this out.
- If changing cover image selection, reset/rebuild visual fingerprints as needed.

## SQLite Vs PostgreSQL

- PostgreSQL path uses `Product.search_text` and database search features.
- SQLite fallback uses `ProductSearchTerm`.
- Keep both paths tested when search logic changes.

