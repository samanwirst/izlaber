# Testing And Verification

## Test Commands

| Scope | Command |
| --- | --- |
| Full test suite | `PYTHONPATH=server:. .venv/bin/pytest` |
| Bot AI/search helpers | `PYTHONPATH=server:. .venv/bin/pytest server/tests/test_bot_ai.py` |
| Bot localization | `PYTHONPATH=server:. .venv/bin/pytest server/tests/test_bot_locales.py` |
| Server ingestion/search | `PYTHONPATH=server:. .venv/bin/pytest server/tests/test_ingestion.py` |
| User preferences | `PYTHONPATH=server:. .venv/bin/pytest server/tests/test_user_preferences.py` |
| Parser normalizer/pipeline units | `PYTHONPATH=server:. .venv/bin/pytest parsers/uzum_market/test_normalizer.py parsers/wildberries/test_normalizer.py` |
| Analytics site typecheck | `cd site && npm run typecheck` |
| Analytics site production build | `cd site && npm run build` |

## Lint

```bash
.venv/bin/ruff check .
.venv/bin/ruff check <paths>
```

Ruff settings live in `pyproject.toml`:

- line length: 100
- target: Python 3.11
- selected rules: `E`, `F`, `I`, `UP`, `B`

## Django Checks

```bash
PYTHONPATH=server python server/manage.py check
PYTHONPATH=server python server/manage.py makemigrations --check
PYTHONPATH=server python server/manage.py migrate
```

## Verification By Change Type

| Change type | Minimum verification |
| --- | --- |
| Docs only | `git diff --check` |
| Bot handler/locales/keyboards | Ruff on touched bot files plus `test_bot_locales.py` or `test_bot_ai.py` |
| Bot API client contract | Bot tests plus matching server API tests |
| Server model | `makemigrations --check`, `migrate`, focused Django tests |
| Server search | `test_ingestion.py` and any new search-specific tests |
| Analytics dashboard | `server/tests/test_analytics_summary.py`, `cd site && npm run typecheck`, `cd site && npm run build` |
| Parser normalization | `parsers/uzum_market/test_normalizer.py`, `parsers/wildberries/test_normalizer.py` |
| Docker/env docs | Inspect `docker-compose.yml`, Dockerfiles, `.env.example`; run Docker only when needed |
| Cross-cutting behavior | Ruff full repo plus full pytest suite |

## Expensive Or Stateful Checks

Avoid these unless explicitly requested or necessary:

- Real full parser crawls.
- Headful browser captcha sessions.
- Full Docker rebuilds when a file read is enough.
- Commands that mutate production-sized local data.

## What To Report

Always say which commands were run and whether they passed. If a relevant check was skipped, state the reason.
