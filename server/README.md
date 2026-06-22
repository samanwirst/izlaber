# Server

Django + DRF backend for normalized marketplace catalog data.

## Local SQLite

```bash
PYTHONPATH=server python server/manage.py migrate
PYTHONPATH=server python server/manage.py createsuperuser
PYTHONPATH=server python server/manage.py runserver 0.0.0.0:8000
```

## PostgreSQL

Set `DATABASE_URL`, for example:

```bash
DATABASE_URL=postgres://izlaber:izlaber@localhost:5432/izlaber
```

## API

Bot/read endpoints:

```text
GET /api/v1/products/
GET /api/v1/products/{id}/
GET /api/v1/marketplaces/
GET /api/v1/categories/
```

Parser/internal endpoints:

```text
POST /api/internal/crawl-runs/start/
POST /api/internal/products/upsert-batch/
POST /api/internal/crawl-runs/{id}/finish/
POST /api/internal/crawl-events/
```

Internal services pass `X-Internal-API-Key`.
