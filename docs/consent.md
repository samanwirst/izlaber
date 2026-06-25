# User Consent

This is an implementation note, not legal advice. Keep the production text reviewed
against the current Uzbekistan requirements before launch.

## Legal Basis Checked

Official Uzbekistan sources used for this implementation:

- Personal data law: `https://www.lex.uz/ru/docs/4396428`
- Advertising law: `https://lex.uz/ru/docs/6052633`
- E-commerce/personal data advertising restriction reference: `https://www.lex.uz/acts/2650295`
- Civil Code contract change rules: `https://lex.uz/docs/111181`
- Consumer protection restrictions on unfair contract terms: `https://lex.uz/ru/docs/14643`

Open Uzbek-market examples reviewed for drafting structure:

- Olcha personal data policy and public offer (`https://olcha.uz/ru/page/policy`,
  `https://olcha.uz/ru/page/public-offer`): data categories, protection measures,
  retention, and unilateral-publication update wording.
- Asaxiy privacy policy (`https://asaxiy.uz/ru/page/privacy-policy`): separated
  processing purposes, legal bases, third-party transfers, advertising/cookie consent,
  and user rights.
- Click privacy policy and public offer (`https://co.click.uz/ru/politika-konfedicialnosti`,
  `https://click.uz/ru/terms`): detailed definitions, data-subject rights, retention,
  Telegram/app service scope, and versioned offer text.
- Uzum seller offer (`https://seller.uzum.uz/seller/agreement/`): privacy-policy
  incorporation and strict treatment of buyer personal data transfers.

Practical rules encoded in the bot:

- Personal data processing needs consent in a form that can confirm the consent was
  received.
- Consent can be revoked; the bot exposes `/consent` and records `revoked_at`.
- Every `accept`, `decline`, and `revoke` action is also appended to
  `UserConsentEvent` so the full consent timeline is retained even when the current
  `UserConsent` state is overwritten by a later action.
- Migration `0012_userconsentevent` backfills only the known timestamps already stored
  in current `UserConsent` rows. Earlier overwritten actions from before this history
  table cannot be reconstructed.
- Advertising through a telecommunications service requires prior subscriber consent.
- Without active consent, the bot does not process search requests.
- Revocation must remain available. Do not hide or disable the revoke action without
  a fresh legal review.
- Legal pages may reserve Izlaber's right to update published rules for future use,
  but changes that materially alter the covered data, processing purposes, advertising
  scope, or any legally consent-gated processing must request fresh consent and bump
  `BOT_CONSENT_VERSION`/`USER_CONSENT_VERSION`.

## Covered Bot Data

The consent prompt covers:

- Telegram user ID and profile language.
- User messages, search queries, photos, and voice messages submitted to search.
- Product-card impressions and click analytics.
- Sponsored advertising and analytics/personalization use.

The public legal pages additionally disclose:

- Temporary AI-provider processing for text, photo, voice, and result ranking when
  `OPENAI_*` features are enabled.
- The aggregator boundary: Izlaber does not sell products directly and does not
  guarantee third-party marketplace price, availability, delivery, warranty, or returns.
- Sponsored campaign measurement and the rule that advertisers may receive campaign
  statistics but not raw Telegram IDs, private messages, original photos, or audio.

## Runtime Behavior

- `BOT_CONSENT_ENABLED=true` enables the aiogram middleware gate.
- Before consent is accepted, the bot shows the consent prompt in Uzbek, Russian, and
  English in one message because it cannot rely on stored language preferences yet.
- The consent prompt must render only one reply keyboard button for acceptance. Policy
  URLs are rendered as text links in the message body, not as inline buttons.
- The acceptance text is a service event. It must be handled by the consent handler
  before generic text search and must not call catalog search, search analytics, or AI
  reranking.
- Revocation is available with `/consent revoke`; do not reintroduce a revoke button
  unless the consent UX is reviewed again.
- `BOT_CONSENT_VERSION` is stored with every user decision.
- `USER_CONSENT_VERSION` is the server fallback/current version; keep it equal to
  `BOT_CONSENT_VERSION`.
- Public policy pages are served by Django at `/legal/privacy/` and
  `/legal/sponsored-ads/`.
- If `BOT_PRIVACY_POLICY_URL` and `BOT_SPONSORED_ADS_POLICY_URL` are empty, the bot
  derives them from `BOT_PUBLIC_BASE_URL`.
- Bump the version when consent text, covered data, analytics scope, or advertising
  scope changes materially.
- `GET /api/v1/user-consents/?active_only=true&version=...` preloads active users.
- `POST /api/v1/user-consents/{telegram_user_id}/` records `accept`, `decline`, or
  `revoke` in the current `UserConsent` state and appends the same action to
  `UserConsentEvent`.
- The bot only caches active user IDs for the current runtime. Server DB remains the
  source of truth.

## Important Limitations

- Telegram chat messages do not provide browser cookies. Cookie-level analytics only
  apply to server redirect links such as `/api/v1/redirect/products/{id}/`.
- If the server API is unavailable, the bot does not mark consent as accepted locally.
  The user must retry after persistence is available.
