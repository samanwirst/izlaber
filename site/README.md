# Izlaber Analytics Site

Next.js analytics dashboard and sponsored campaign console for professional analysts,
strategists, and marketers.

The site fetches aggregated data server-side from Django:

```text
GET /api/v1/analytics/summary/?days=30
X-Internal-API-Key: <ANALYTICS_API_KEY or BOT_API_KEY>
```

It also manages sponsored bot placements through:

```text
GET/POST /api/v1/sponsored-campaigns/
GET/PATCH /api/v1/sponsored-campaigns/{id}/
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
SITE_ADMIN_USERNAME=admin
SITE_ADMIN_PASSWORD=admin
SITE_ADMIN_TELEGRAM_IDS=976835256
SITE_AUTH_SECRET=<random-secret>
TELEGRAM_BOT_TOKEN=<bot token used to send login codes>
```

In Docker Compose, `SERVER_API_BASE_URL` points to `http://server:8000/api`.

Dashboard access is protected by username/password plus an 8-symbol Telegram code.
Codes are sent only to Telegram IDs listed in `SITE_ADMIN_TELEGRAM_IDS`.
