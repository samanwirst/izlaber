# Izlaber Analytics Site

Next.js analytics dashboard for professional analysts, strategists, and marketers.

The site fetches aggregated data server-side from Django:

```text
GET /api/v1/analytics/summary/?days=30
X-Internal-API-Key: <ANALYTICS_API_KEY or BOT_API_KEY>
```

Local development:

```bash
cd site
npm install
npm run dev
```

Required environment:

```text
SERVER_API_BASE_URL=http://127.0.0.1:8000/api
ANALYTICS_API_KEY=<internal key>
```

In Docker Compose, `SERVER_API_BASE_URL` points to `http://server:8000/api`.
