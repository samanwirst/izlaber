# Common Pitfalls

## Dangerous Mistakes To Avoid

| Mistake | Why it hurts | Correct approach |
| --- | --- | --- |
| Reading or printing `.env` | Can expose real API keys and bot tokens. | Use `.env.example` for variable names. |
| Running `docker compose down -v` | Deletes PostgreSQL `pgdata` volume. | Use `docker compose down`. |
| Letting bot import Django models | Breaks service boundary and Docker/runtime assumptions. | Add server API endpoint/client method. |
| Letting parser write DB directly | Skips crawl run stats, auth, deltas, and deactivation rules. | Write through `/api/internal/`. |
| Full parser crawl for a quick check | Slow, stateful, captcha-prone. | Use unit tests, dry run, or limited test mode. |
| Forgetting all three locales | Users can see mixed languages. | Update Uzbek, Russian, English in `bot/locales.py`. |
| Changing product model without migration | Runtime schema mismatch. | Commit migration and run migrate/checks. |
| Changing search fields without rebuild plan | Old rows may stay stale. | Run or document search/visual index rebuild. |
| Returning full products from list API | Slows bot search. | Keep list payload compact. |
| Unbounded AI candidate/image/audio flow | Cost and latency spikes. | Keep limits/timeouts and fallback paths. |
| Allowing parallel bot searches per user | Telegram spam can start many expensive AI/API handlers before sliding-window limits react. | Preserve the bot in-flight search gate and test it when changing middleware. |
| Enabling analytics cookies without consent/policy | Creates legal and trust risk. | Keep cookies off by default until privacy text and consent are ready. |

## Files To Avoid Touching Casually

- `.env`, `.env.*`
- `server/db.sqlite3`
- `.parser_state/`
- `bot/venv/`, `.venv/`, `venv/`
- `__pycache__/`, `.ruff_cache/`, `.pytest_cache/`
- Generated migration files unless the model change requires them

## Parser-Specific Notes

- Captcha handling is manual in headful browser mode.
- The crawler seeds and reuses a runtime Chrome profile.
- Checkpoint files are local runtime data.
- Limited runs are for testing and must not trigger product deactivation.

## Bot-Specific Notes

- `More` text/button aliases should stay short and exact to avoid treating normal user requests as pagination.
- Search state is in memory and intentionally resets on process restart.
- User language is persistent through the server API, not local files.
- Product click analytics require `BOT_PUBLIC_BASE_URL`; without it the bot keeps direct product links.

## Server-Specific Notes

- `ProductSearchTerm` is mainly for SQLite fallback; PostgreSQL search uses `Product.search_text`.
- `cover_image_url` should be the product card cover, not an arbitrary gallery image.
- `canonical_url` is required for cards and should point to the product page.
