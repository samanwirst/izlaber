# Development Workflow

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Fill only local secrets in `.env`. Do not commit `.env`.

## Run Locally Without Docker

Server:

```bash
PYTHONPATH=server python server/manage.py migrate
PYTHONPATH=server python server/manage.py runserver 0.0.0.0:8000
```

Bot:

```bash
python -m bot
```

Analytics site:

```bash
cd site
npm install
npm run dev
```

Parser test mode:

```bash
python -m parsers.uzum_market.cli crawl --mode test --limit 100
```

## Run With Docker

```bash
./scripts/docker-start.sh server bot site
docker compose logs -f server
docker compose logs -f bot
docker compose logs -f site
docker compose down
```

Notes:

- Compose starts PostgreSQL and stores data in the `pgdata` named volume.
- The analytics site is exposed on `SITE_PORT` (`3000` by default).
- `docker compose down` keeps `pgdata`.
- `docker compose down -v` removes `pgdata`; do not use it casually.
- The parser service is behind the `parser` profile.

Parser in Docker:

```bash
docker compose --profile parser run --rm parser python -m parsers.uzum_market.cli crawl --mode test --limit 100
```

## Common Maintenance Commands

```bash
./scripts/rebuild_product_search_index.sh --marketplace uzum
./scripts/rebuild_product_visual_index.sh --marketplace uzum
./scripts/audit_uzum_catalog.sh --require-checkpoint
python -m bot.setup_profile
```

Run `python -m bot.setup_profile` after changing bot profile names, descriptions, command descriptions, `/start`, or `/help` copy.

## Git Workflow For Agents

1. Check `git status -sb` before editing.
2. Keep documentation-only changes separate from product changes.
3. Do not revert user changes.
4. Stage explicit paths, not `git add -A`, when the worktree is mixed.
5. Run scoped verification before final response.
