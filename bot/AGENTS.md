# bot/AGENTS.md

Rules for bot work:

- The bot must not import Django models, server apps, or parser modules.
- All catalog reads and user preference writes go through `bot.services.api_client.ServerAPIClient`.
- Keep Telegram copy in `bot/locales.py`; update Uzbek, Russian, and English together.
- Preserve per-chat/per-user pagination isolation in `bot/services/search_state.py`.
- Keep AI usage cost-aware: local indexed search should remain the first path unless config says otherwise.
- Never log bot tokens, OpenAI keys, Telegram file URLs, or raw user secrets.

Useful focused checks:

```bash
.venv/bin/ruff check bot server/tests/test_bot_ai.py server/tests/test_bot_locales.py
PYTHONPATH=server:. .venv/bin/pytest server/tests/test_bot_ai.py server/tests/test_bot_locales.py
```

