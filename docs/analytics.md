# Analytics

Izlaber stores analytics in `catalog_analyticsevent` and exposes aggregated reporting in
the Next.js dashboard under `site/`.

## Stored Event Types

| Event | Source | Meaning |
| --- | --- | --- |
| `bot_start` | Bot | User started the bot. |
| `bot_help` | Bot | User opened help. |
| `language_prompt` | Bot | User opened language picker. |
| `language_select` | Bot | User selected a language. |
| `search` | Bot | User searched by text or recognized voice text. |
| `photo_search` | Bot | User sent a photo search request. |
| `voice_search` | Bot | User sent a voice search request. |
| `search_no_results` | Bot | Search completed with no products. |
| `more_results` | Bot | User requested next results by button or text alias. |
| `view_item_list` | Bot | A product card was shown to a user. |
| `select_item` | Redirect | User clicked a tracked product card link. |
| `sponsored_impression` | Bot | A clearly labeled sponsored product card was shown. |
| `sponsored_click` | Redirect | User clicked a sponsored product card link. |

`search`, `view_item_list`, and `select_item` intentionally match common ecommerce analytics naming.

## Privacy And Legal Guardrails

- Telegram bots do not provide browser cookies in chat. Cookie-level attribution only exists after a user opens a tracked redirect URL.
- `ANALYTICS_COOKIE_ENABLED=false` by default. Enable it only after analytics cookie consent/privacy text is in place.
- Raw IP addresses are not stored. `ANALYTICS_HASH_IP=true` stores only salted hashes for redirect requests.
- Avoid storing photo bytes, audio bytes, bot tokens, OpenAI keys, or private `.env` values in analytics metadata.

References:

- Telegram Bot API: https://core.telegram.org/bots/api
- Telegram Mini Apps data validation: https://core.telegram.org/bots/webapps
- Google Analytics ecommerce events: https://developers.google.com/analytics/devguides/collection/ga4/ecommerce
- EU cookie consent guidance example: https://ec.europa.eu/eurostat/web/user-guides/data-browser/introduction-navigation-data/manage-cookies
- ICO lawful basis guidance: https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/childrens-information/childrens-code-guidance-and-resources/age-appropriate-design-a-code-of-practice-for-online-services/annex-c-lawful-basis-for-processing/

## Click Tracking

Set `BOT_PUBLIC_BASE_URL` to the public server origin, for example:

```bash
BOT_PUBLIC_BASE_URL=https://example.com
```

The bot then sends product links like:

```text
https://example.com/api/v1/redirect/products/{product_id}/?ctx={analytics_event_id}
```

The server stores `select_item` and redirects to the product's `canonical_url`.

## Sponsored Campaigns

Sponsored campaigns are stored in `catalog_sponsoredcampaign` and managed through the
analytics site or Django admin. A campaign targets one active product, one or more
keywords, optional language codes, optional start/end timestamps, priority, and daily
or total impression caps.

Bot placement lookup:

```text
GET /api/v1/sponsored-placements/?q=iphone&language_code=ru&limit=1
X-Internal-API-Key: <BOT_API_KEY>
```

Management endpoints:

```text
GET/POST /api/v1/sponsored-campaigns/
GET/PATCH /api/v1/sponsored-campaigns/{id}/
```

Operational rules:

- Sponsored cards must keep the localized `Sponsored offer` / `Рекламное предложение`
  label.
- Do not silently merge sponsored performance into organic `view_item_list` or
  `select_item` metrics.
- `BOT_SPONSORED_SEARCH_LIMIT=0` disables sponsored placement in the bot.
