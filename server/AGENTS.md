# server/AGENTS.md

Rules for server work:

- The server owns database models, migrations, search indexes, and API contracts.
- Bot-facing read endpoints use `BotAPIKeyAuthentication`.
- Parser-facing ingestion endpoints use `ParserAPIKeyAuthentication`.
- Commit Django migrations with model changes.
- Keep expensive product list responses lightweight; `ProductViewSet.list` intentionally uses a compact serializer/queryset.
- Rebuild search or visual indexes after schema/import changes when the affected fields require it.

Useful focused checks:

```bash
.venv/bin/ruff check server
PYTHONPATH=server python server/manage.py check
PYTHONPATH=server:. .venv/bin/pytest server/tests
```

