# Code Style And Conventions

## Python Style

- Follow the existing Python style in nearby files.
- Ruff is the active linter. Settings live in `pyproject.toml`.
- Keep line length at or below 100 unless an existing pattern justifies otherwise.
- Prefer explicit dataclasses for small config/DTO objects, matching current bot/parser style.
- Keep helper functions close to the module that owns the behavior unless reuse is real.

## Imports

- Let Ruff's `I` rules drive import ordering.
- Do not introduce cross-boundary imports:
  - `bot/` must not import Django apps or parser modules.
  - `server/` must not import bot handlers/services or parser runtime modules.
  - `parsers/` must not import Django models.

## Naming

| Area | Convention |
| --- | --- |
| Marketplace code | Use slug strings such as `uzum`. |
| Source product IDs | Store as strings once normalized. |
| Env vars | Uppercase, service-prefixed where practical: `BOT_*`, `OPENAI_*`, `UZUM_*`. |
| Django models | Singular model names, normal Django conventions. |
| Tests | `test_*.py` files with descriptive `test_...` functions. |

## Bot Copy

- User-facing copy belongs in `bot/locales.py`.
- Update Uzbek, Russian, and English together.
- Keep Telegram parse mode in mind; current default is HTML.
- Escape user-provided text before rendering HTML. Existing helpers already do this in product rendering and `format_message`.

## Error Handling

- Bot API failures should raise or handle `ServerAPIError`.
- OpenAI quota/billing failures should leave local search available.
- Parser failures should be recorded in crawl run status/events when possible.
- Avoid `print` for service diagnostics; use logging.

## Dependencies

- Runtime dependencies are in `pyproject.toml`; server Docker currently installs `server/requirements.txt`.
- If adding a dependency used by the server image, update both places or document why only one is needed.
- Prefer standard library or existing dependencies when the change is small.

