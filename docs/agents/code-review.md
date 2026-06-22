# Code Review Guide

Use this checklist when asked to review changes in this repository.

## Highest-Risk Areas

| Area | Review focus |
| --- | --- |
| Product upsert/deactivation | Avoid accidental mass deactivation or rewriting unchanged products. |
| Search ranking | Keep candidate limits bounded and verify fallback behavior without AI. |
| Bot pagination | Ensure `More` only continues the latest query for the same chat/user. |
| Language persistence | Confirm DB-backed preferences survive bot/container restarts. |
| Photo/voice search | Check download size/time limits, AI fallback, and noisy generic matches. |
| API auth | Internal endpoints must require the correct API key. |
| Parser browser state | Do not delete or commit `.parser_state/`; preserve resume semantics. |
| Docker volumes | Avoid `down -v` unless explicit. |

## Review Output Shape

When reviewing:

1. List findings first, ordered by severity.
2. Include file and line references.
3. Explain user-visible or data-risk impact.
4. Mention missing tests for changed behavior.
5. Keep summaries short and secondary.

## Common Test Expectations

- Bot UX or localization: `server/tests/test_bot_locales.py`.
- Bot AI/search helpers: `server/tests/test_bot_ai.py`.
- Server ingestion/search: `server/tests/test_ingestion.py`.
- User language persistence: `server/tests/test_user_preferences.py`.
- Parser normalization/crawl units: `parsers/uzum_market/test_normalizer.py`.

