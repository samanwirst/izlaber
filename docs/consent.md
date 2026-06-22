# User Consent

This is an implementation note, not legal advice. Keep the production text reviewed
against the current Uzbekistan requirements before launch.

## Legal Basis Checked

Official Uzbekistan sources used for this implementation:

- Personal data law: `https://www.lex.uz/ru/docs/4396428`
- Advertising law: `https://lex.uz/uz/docs/6052633`
- E-commerce/personal data advertising restriction reference: `https://www.lex.uz/acts/2650295`

Practical rules encoded in the bot:

- Personal data processing needs consent in a form that can confirm the consent was
  received.
- Consent can be revoked; the bot exposes `/consent` and records `revoked_at`.
- Advertising through a telecommunications service requires prior subscriber consent.
- Without active consent, the bot does not process search requests.

## Covered Bot Data

The consent prompt covers:

- Telegram user ID and profile language.
- User messages, search queries, photos, and voice messages submitted to search.
- Product-card impressions and click analytics.
- Sponsored advertising and analytics/personalization use.

## Runtime Behavior

- `BOT_CONSENT_ENABLED=true` enables the aiogram middleware gate.
- `BOT_CONSENT_VERSION` is stored with every user decision.
- `USER_CONSENT_VERSION` is the server fallback/current version; keep it equal to
  `BOT_CONSENT_VERSION`.
- Bump the version when consent text, covered data, analytics scope, or advertising
  scope changes materially.
- `GET /api/v1/user-consents/?active_only=true&version=...` preloads active users.
- `POST /api/v1/user-consents/{telegram_user_id}/` records `accept`, `decline`, or
  `revoke`.
- The bot only caches active user IDs for the current runtime. Server DB remains the
  source of truth.

## Important Limitations

- Telegram chat messages do not provide browser cookies. Cookie-level analytics only
  apply to server redirect links such as `/api/v1/redirect/products/{id}/`.
- If the server API is unavailable, the bot does not mark consent as accepted locally.
  The user must retry after persistence is available.
