import asyncio
from dataclasses import replace
from datetime import datetime
from uuid import UUID

import pytest
from aiogram.types import Chat, Message, PhotoSize, User, Voice
from django.conf import settings

from bot.config import BotConfig, Config, _policy_url
from bot.handlers import common as common_handlers
from bot.handlers.admin import _format_usd, _is_openai_status_admin
from bot.handlers.common import (
    _cover_image_to_jpeg,
    _cover_url_needs_jpeg_upload,
    _expansion_filters,
    _is_unknown_slash_command,
    _local_results_need_ai,
    _merge_unique_products,
    _photo_candidate_query_limit,
    _photo_exact_candidate_products,
    _photo_result_intro_key,
    _photo_search_queries,
    _photo_substitute_queries,
    _photo_text_fallback_products,
    _query_requirements,
    _replace_status_message,
    _run_text_search_with_timeout,
    _search_expansion_allowed,
    _select_photo_for_vision,
    _send_search_progress_pings,
    _source_product_ids_from_text,
    _strip_bot_username,
    _voice_search_available,
)
from bot.keyboards.main_menu import more_results_keyboard
from bot.middlewares import rate_limit as rate_limit_middleware
from bot.middlewares.consent import _is_consent_event
from bot.middlewares.rate_limit import (
    AI_SCOPE,
    GENERAL_SCOPE,
    SEARCH_SCOPE,
    RateLimitMiddleware,
    _admin_bypasses_limit,
    _event_rules,
    _event_scopes,
    _format_retry_after,
)
from bot.services import ai_reranker as ai_reranker_service
from bot.services.ai_audio import _language_name, _transcription_prompt
from bot.services.ai_reranker import (
    OPENAI_PROBE_MAX_OUTPUT_TOKENS,
    SearchExpansion,
    SearchQueryUnderstanding,
    _is_quota_exhausted_response,
    _local_query_understanding,
    _parse_search_expansions,
    _query_needs_understanding,
    _rank_products_from_ids,
    rerank_products,
    understand_search_query,
)
from bot.services.ai_runtime import AIRuntimeState
from bot.services.ai_vision import PhotoSearchQuery, parse_photo_search_output
from bot.services.api_client import (
    ProductDTO,
    _response_rows,
    product_click_url,
    render_product_card,
)
from bot.services.consent_store import UserConsentStore
from bot.services.openai_billing import OpenAICostSummary, _merge_cost_buckets
from bot.services.rate_limit import RateLimitRule, SlidingWindowRateLimiter, UserInFlightGate
from bot.services.search_state import SearchStateStore


def product(product_id: int, title: str) -> ProductDTO:
    return ProductDTO(
        id=product_id,
        title=title,
        canonical_url=f"https://uzum.uz/ru/product/test-{product_id}",
        cover_image_url=None,
        marketplace_code="uzum",
        marketplace_name="Uzum Market",
        marketplace_base_url="https://uzum.uz",
        brand=None,
        current_price=None,
        old_price=None,
        currency="UZS",
        rating=None,
        reviews_count=None,
        category_path_text=None,
    )


def test_api_client_response_rows_accepts_list_and_paginated_dict():
    rows = [{"id": 1}]

    assert _response_rows(rows) == rows
    assert _response_rows({"results": rows}) == rows
    assert _response_rows({"results": None}) == []


def test_product_card_can_render_tracking_link():
    context_event_id = UUID("11111111-1111-1111-1111-111111111111")
    tracking_url = product_click_url(
        public_base_url="https://izlaber.example",
        product_id=123,
        context_event_id=context_event_id,
    )
    item = product(123, "Tracked product")
    item = replace(item, tracking_url=tracking_url)

    assert tracking_url == (
        "https://izlaber.example/api/v1/redirect/products/123/"
        "?ctx=11111111-1111-1111-1111-111111111111"
    )
    assert tracking_url in render_product_card(item, 1, "en")


def test_product_card_renders_sponsored_label():
    item = replace(
        product(123, "Sponsored product"),
        sponsored_campaign_id=7,
        sponsored_campaign_name="Test campaign",
        sponsored_advertiser_name="Test Seller",
    )

    card = render_product_card(item, 1, "ru")

    assert card.startswith("<i>Рекламное предложение</i>\n")
    assert "Sponsored product" in card


def test_product_card_uses_production_layout_without_old_price_or_marketplace():
    item = replace(
        product(123, "Phone case"),
        current_price="25000.00",
        old_price="40000.00",
        rating="4.90",
        reviews_count=17,
        category_path_text="Аксессуары",
    )

    card = render_product_card(
        item,
        1,
        "ru",
        marketplace_custom_emoji_ids={"uzum": "5368324170671202286"},
    )

    assert '<tg-emoji emoji-id="5368324170671202286">' in card
    assert '<a href="https://uzum.uz/ru/product/test-123">Phone case</a></b>\n\nЦена:' in card
    assert "Старая цена" not in card
    assert "40 000" not in card
    assert "Маркетплейс" not in card
    assert "Uzum Market" not in card
    assert "Рейтинг 4.90, 17 отзывов" in card


def test_webp_product_cover_is_converted_to_jpeg_for_telegram():
    from io import BytesIO

    from PIL import Image

    source = BytesIO()
    Image.new("RGBA", (16, 16), (120, 40, 20, 255)).save(source, format="WEBP")

    jpeg_bytes = _cover_image_to_jpeg(source.getvalue())

    assert _cover_url_needs_jpeg_upload(
        "https://basket-15.wbbasket.ru/vol2371/part237194/237194752/images/c516x688/1.webp"
    )
    assert not _cover_url_needs_jpeg_upload("https://images.uzum.uz/test/t_product_540_high.jpg")
    assert jpeg_bytes is not None
    assert jpeg_bytes.startswith(b"\xff\xd8")
    with Image.open(BytesIO(jpeg_bytes)) as converted:
        assert converted.format == "JPEG"


def test_policy_urls_are_derived_from_public_base_url():
    assert _policy_url("", "https://izlaber.example", "/legal/privacy/") == (
        "https://izlaber.example/legal/privacy/"
    )
    assert _policy_url(None, "", "/legal/privacy/") == ""
    assert (
        _policy_url(
            "https://static.example/privacy",
            "https://izlaber.example",
            "/legal/privacy/",
        )
        == "https://static.example/privacy"
    )


@pytest.mark.asyncio
async def test_ai_rerank_falls_back_without_api_key():
    config = Config(bot=BotConfig(token="test"), openai_api_key="")
    products = [product(1, "A"), product(2, "B")]

    assert await rerank_products(query="phone", products=products, config=config) == products


def test_query_understanding_extracts_product_intent_from_story():
    query = (
        "Я как то был в Турции и увидел очень красивую тарелку из интересного "
        "зеленого камня. Я не знаю, что это был за камень, но он очень красивый. "
        "Эта тарелка она переливалась словно кольцами и я бы хотел ее к себе домой"
    )

    assert _query_needs_understanding(query) is True

    result = _local_query_understanding(query)

    assert result.query == "зеленая тарелка камень"
    assert result.source == "local"
    assert [expansion.query for expansion in result.search_queries] == [
        "зеленая тарелка камень",
        "тарелка зеленая камень",
        "зеленая тарелка",
    ]


@pytest.mark.asyncio
async def test_understand_search_query_uses_ai_only_for_narrative(monkeypatch):
    calls: list[str] = []

    async def fake_request_query_understanding(*, query, config):
        calls.append(query)
        return SearchQueryUnderstanding(
            query="зеленая каменная тарелка",
            search_queries=[SearchExpansion("зеленая каменная тарелка")],
            source="ai",
        )

    monkeypatch.setattr(ai_reranker_service, "_enabled", lambda _config: True)
    monkeypatch.setattr(
        ai_reranker_service,
        "_request_query_understanding",
        fake_request_query_understanding,
    )
    config = Config(bot=BotConfig(token="test"), openai_api_key="key")

    direct = await understand_search_query(query="чехол на телефон", config=config)
    narrative = await understand_search_query(
        query="Я видел красивую зеленую тарелку из камня и хочу такую домой.",
        config=config,
    )

    assert direct.query == "чехол на телефон"
    assert direct.source == "original"
    assert narrative.query == "зеленая каменная тарелка"
    assert calls == ["Я видел красивую зеленую тарелку из камня и хочу такую домой."]


@pytest.mark.asyncio
async def test_understand_search_query_can_force_ai_for_short_query(monkeypatch):
    calls: list[str] = []

    async def fake_request_query_understanding(*, query, config):
        calls.append(query)
        return SearchQueryUnderstanding(
            query="Windows 10 лицензионный ключ",
            search_queries=[
                SearchExpansion("Windows 10 лицензионный ключ"),
                SearchExpansion("Windows 10 Pro ключ"),
            ],
            source="ai",
        )

    monkeypatch.setattr(ai_reranker_service, "_enabled", lambda _config: True)
    monkeypatch.setattr(
        ai_reranker_service,
        "_request_query_understanding",
        fake_request_query_understanding,
    )

    direct = await understand_search_query(
        query="виндовс 10",
        config=Config(bot=BotConfig(token="test"), openai_api_key="key"),
    )
    forced = await understand_search_query(
        query="виндовс 10",
        config=Config(bot=BotConfig(token="test"), openai_api_key="key"),
        force_ai=True,
    )

    assert direct.query == "виндовс 10"
    assert direct.source == "original"
    assert forced.query == "Windows 10 лицензионный ключ"
    assert [expansion.query for expansion in forced.search_queries] == [
        "Windows 10 лицензионный ключ",
        "Windows 10 Pro ключ",
    ]
    assert calls == ["виндовс 10"]


@pytest.mark.asyncio
async def test_text_search_uses_understood_query_for_candidates(monkeypatch):
    original_query = (
        "Я как то был в Турции и увидел очень красивую тарелку из интересного "
        "зеленого камня. Я не знаю, что это был за камень."
    )
    searched_queries: list[str] = []
    sent_queries: list[str] = []
    tracked_events: list[tuple[str, str]] = []

    async def fake_understand_search_query(*, query, config):
        assert query == original_query
        return SearchQueryUnderstanding(
            query="зеленая каменная тарелка",
            search_queries=[
                SearchExpansion("зеленая каменная тарелка"),
                SearchExpansion("тарелка из зеленого камня"),
            ],
            source="ai",
        )

    async def fake_load_ranked_candidates(**kwargs):
        searched_queries.append(kwargs["query"])
        return [product(1, "Круглая тарелка, зеленая")]

    async def fake_load_understanding_expanded_products(**_kwargs):
        return []

    async def fake_load_sponsored_products(**_kwargs):
        return []

    async def fake_track_message_event(**kwargs):
        tracked_events.append((kwargs["event_type"], kwargs["query"]))

    async def fake_replace_status_message(*_args, **_kwargs):
        return None

    async def fake_send_products(_message, _products, **kwargs):
        sent_queries.append(kwargs["query"])

    monkeypatch.setattr(common_handlers, "understand_search_query", fake_understand_search_query)
    monkeypatch.setattr(common_handlers, "_load_ranked_candidates", fake_load_ranked_candidates)
    monkeypatch.setattr(
        common_handlers,
        "_load_understanding_expanded_products",
        fake_load_understanding_expanded_products,
    )
    monkeypatch.setattr(common_handlers, "_load_sponsored_products", fake_load_sponsored_products)
    monkeypatch.setattr(common_handlers, "track_message_event", fake_track_message_event)
    monkeypatch.setattr(common_handlers, "_replace_status_message", fake_replace_status_message)
    monkeypatch.setattr(common_handlers, "_send_products", fake_send_products)

    message = Message(
        message_id=1,
        date=datetime.now(),
        chat=Chat(id=10, type="private"),
        from_user=User(id=1, is_bot=False, first_name="Test", language_code="ru"),
        text=original_query,
    )

    await common_handlers._run_text_search(
        message=message,
        config=Config(bot=BotConfig(token="test"), openai_api_key="key"),
        query=original_query,
        status_message=object(),
    )

    assert searched_queries == ["зеленая каменная тарелка"]
    assert sent_queries == ["зеленая каменная тарелка"]
    assert ("search", original_query) in tracked_events
    assert ("search_query_understood", "зеленая каменная тарелка") in tracked_events


def test_search_state_isolated_by_user():
    store = SearchStateStore()
    first_products = [product(1, "First")]
    second_products = [product(2, "Second")]

    store.set(
        chat_id=10,
        user_id=1,
        query="iphone",
        products=first_products,
        offset=1,
        candidate_offset=30,
    )
    store.set(
        chat_id=10,
        user_id=2,
        query="notebook",
        products=second_products,
        offset=1,
        candidate_offset=30,
    )

    assert store.get(chat_id=10, user_id=1).query == "iphone"
    assert store.get(chat_id=10, user_id=1).products == first_products
    assert store.get(chat_id=10, user_id=2).query == "notebook"
    assert store.get(chat_id=10, user_id=2).products == second_products


@pytest.mark.asyncio
async def test_user_consent_store_preloads_and_updates_cache():
    class Client:
        async def load_active_user_consents(self, consent_version):
            assert consent_version == "test-v1"
            return {1, 2}

        async def set_user_consent(
            self,
            *,
            telegram_user_id,
            action,
            consent_version,
            language_code,
        ):
            assert telegram_user_id == 1
            assert action == "revoke"
            assert consent_version == "test-v1"
            assert language_code == "ru"
            return False

    store = UserConsentStore()
    await store.preload(Client(), "test-v1")

    assert store.has_active(1) is True
    assert store.has_active(3) is False

    active = await store.set_consent(
        user_id=1,
        action="revoke",
        consent_version="test-v1",
        language_code="ru",
        client=Client(),
    )

    assert active is False
    assert store.has_active(1) is False


def test_consent_middleware_only_allows_exact_consent_command():
    consent_message = Message(
        message_id=1,
        date=datetime.now(),
        chat=Chat(id=1, type="private"),
        text="/consent",
    )
    targeted_consent_message = Message(
        message_id=2,
        date=datetime.now(),
        chat=Chat(id=1, type="private"),
        text="/consent@TestBot",
    )
    bypass_attempt = Message(
        message_id=3,
        date=datetime.now(),
        chat=Chat(id=1, type="private"),
        text="/consentfoo iphone",
    )
    accept_button_message = Message(
        message_id=4,
        date=datetime.now(),
        chat=Chat(id=1, type="private"),
        text="✅ Roziman / Согласен / I agree",
    )

    assert _is_consent_event(consent_message) is True
    assert _is_consent_event(targeted_consent_message) is True
    assert _is_consent_event(accept_button_message) is True
    assert _is_consent_event(bypass_attempt) is False


@pytest.mark.asyncio
async def test_replace_status_message_sends_new_message_for_reply_keyboard():
    class FakeMessage:
        def __init__(self) -> None:
            self.deleted = False
            self.edited: list[tuple[str, bool]] = []
            self.answered: list[tuple[str, object | None, bool]] = []

        async def delete(self) -> None:
            self.deleted = True

        async def edit_text(self, text, disable_web_page_preview=True):
            self.edited.append((text, disable_web_page_preview))

        async def answer(self, text, reply_markup=None, disable_web_page_preview=True):
            self.answered.append((text, reply_markup, disable_web_page_preview))

    message = FakeMessage()
    keyboard = more_results_keyboard("ru")

    await _replace_status_message(
        message,
        "Найдено 10 товаров.",
        language="ru",
        reply_markup=keyboard,
    )

    assert message.deleted is True
    assert message.edited == []
    assert message.answered == [("Найдено 10 товаров.", keyboard, True)]


@pytest.mark.asyncio
async def test_search_progress_pings_use_requested_schedule(monkeypatch):
    delays: list[float] = []

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    class FakeMessage:
        def __init__(self) -> None:
            self.answered: list[tuple[str, bool]] = []

        async def answer(self, text, disable_web_page_preview=True):
            self.answered.append((text, disable_web_page_preview))

    monkeypatch.setattr(common_handlers.asyncio, "sleep", fake_sleep)
    message = FakeMessage()

    await _send_search_progress_pings(message, "ru")

    assert delays == [5, 10, 10, 10, 10, 10]
    assert message.answered == [("все еще ищу....", True)] * 6


def test_rate_limit_event_scopes_target_search_and_ai_inputs():
    text_message = Message(
        message_id=1,
        date=datetime.now(),
        chat=Chat(id=1, type="private"),
        text="iphone",
    )
    more_message = Message(
        message_id=2,
        date=datetime.now(),
        chat=Chat(id=1, type="private"),
        text="ещё",
    )
    command_message = Message(
        message_id=3,
        date=datetime.now(),
        chat=Chat(id=1, type="private"),
        text="/start",
    )
    photo_message = Message(
        message_id=4,
        date=datetime.now(),
        chat=Chat(id=1, type="private"),
        photo=[
            PhotoSize(file_id="photo", file_unique_id="photo-1", width=200, height=200),
        ],
    )
    voice_message = Message(
        message_id=5,
        date=datetime.now(),
        chat=Chat(id=1, type="private"),
        voice=Voice(file_id="voice", file_unique_id="voice-1", duration=5),
    )
    consent_accept_message = Message(
        message_id=6,
        date=datetime.now(),
        chat=Chat(id=1, type="private"),
        text="✅ Roziman / Согласен / I agree",
    )

    assert SEARCH_SCOPE in _event_scopes(text_message)
    assert SEARCH_SCOPE in _event_scopes(more_message)
    assert SEARCH_SCOPE not in _event_scopes(command_message)
    assert SEARCH_SCOPE not in _event_scopes(consent_accept_message)
    assert {SEARCH_SCOPE, AI_SCOPE}.issubset(_event_scopes(photo_message))
    assert {SEARCH_SCOPE, AI_SCOPE}.issubset(_event_scopes(voice_message))


def test_rate_limit_text_search_with_ai_uses_ai_scope():
    config = Config(bot=BotConfig(token="test"))
    text_message = Message(
        message_id=1,
        date=datetime.now(),
        chat=Chat(id=1, type="private"),
        text="iphone",
    )
    more_message = Message(
        message_id=2,
        date=datetime.now(),
        chat=Chat(id=1, type="private"),
        text="ещё",
    )

    text_scopes = {rule.scope for rule in _event_rules(text_message, config)}
    more_scopes = {rule.scope for rule in _event_rules(more_message, config)}

    assert {GENERAL_SCOPE, SEARCH_SCOPE, AI_SCOPE}.issubset(text_scopes)
    assert SEARCH_SCOPE in more_scopes
    assert AI_SCOPE not in more_scopes


def test_admin_bypass_does_not_apply_to_search_or_ai_scopes():
    config = Config(bot=BotConfig(token="test"), openai_status_notify_user_id=976835256)

    assert _admin_bypasses_limit(976835256, config, scopes={GENERAL_SCOPE}) is True
    assert _admin_bypasses_limit(976835256, config, scopes={SEARCH_SCOPE}) is False
    assert _admin_bypasses_limit(976835256, config, scopes={AI_SCOPE}) is False


@pytest.mark.asyncio
async def test_rate_limit_blocks_parallel_search_for_same_user(monkeypatch):
    monkeypatch.setattr(rate_limit_middleware, "rate_limiter", SlidingWindowRateLimiter())
    monkeypatch.setattr(rate_limit_middleware, "search_inflight_gate", UserInFlightGate())
    notices: list[int] = []

    async def fake_notice(event: Message) -> None:
        notices.append(event.message_id)

    monkeypatch.setattr(rate_limit_middleware, "_send_search_in_progress_notice", fake_notice)

    middleware = RateLimitMiddleware()
    config = Config(bot=BotConfig(token="test"))
    first_started = asyncio.Event()
    release_first = asyncio.Event()
    handler_calls = 0

    async def handler(event: Message, data: dict[str, object]) -> str:
        nonlocal handler_calls
        handler_calls += 1
        first_started.set()
        await release_first.wait()
        return "ok"

    first_message = Message(
        message_id=1,
        date=datetime.now(),
        chat=Chat(id=10, type="private"),
        text="iphone",
    )
    second_message = Message(
        message_id=2,
        date=datetime.now(),
        chat=Chat(id=10, type="private"),
        text="noutbuk",
    )

    first_task = asyncio.create_task(middleware(handler, first_message, {"config": config}))
    await first_started.wait()

    blocked = await middleware(handler, second_message, {"config": config})
    release_first.set()

    assert blocked is None
    assert await first_task == "ok"
    assert handler_calls == 1
    assert notices == [2]


def test_sliding_window_rate_limiter_rolls_back_partial_many_checks():
    now = 100.0

    def clock() -> float:
        return now

    limiter = SlidingWindowRateLimiter(clock=clock)
    general = RateLimitRule(scope="general", max_events=10, window_seconds=60)
    search = RateLimitRule(scope="search", max_events=1, window_seconds=60)

    assert limiter.check_many(user_id=1, rules=[general, search]).allowed is True
    blocked = limiter.check_many(user_id=1, rules=[general, search])

    assert blocked.allowed is False
    assert blocked.scope == "search"
    assert limiter.check(user_id=1, rule=general).allowed is True


def test_retry_after_format_is_localized():
    assert _format_retry_after(5, "ru") == "5 сек."
    assert _format_retry_after(65, "en") == "2 min"
    assert _format_retry_after(60, "uz") == "1 daqiqa"


def test_guest_query_strips_bot_username():
    assert _strip_bot_username("@MarketBot iphone 15", "marketbot") == "iphone 15"
    assert _strip_bot_username("найди @MarketBot ноутбук", "marketbot") == "найди ноутбук"
    assert _strip_bot_username("чехол @otherbot", "marketbot") == "чехол @otherbot"


def test_unknown_slash_command_is_not_treated_as_search():
    message = Message(
        message_id=1,
        date=datetime.now(),
        chat=Chat(id=10, type="private"),
        text="/bot аниме постер",
    )

    assert _is_unknown_slash_command(message) is True


@pytest.mark.asyncio
async def test_text_search_timeout_replaces_status_message(monkeypatch):
    async def slow_search(**_kwargs):
        await asyncio.sleep(0.05)

    replacements: list[str] = []
    events: list[str] = []

    async def fake_replace(_status_message, text, **_kwargs):
        replacements.append(text)

    async def fake_track(**kwargs):
        events.append(kwargs["event_type"])

    monkeypatch.setattr(common_handlers, "_run_text_search", slow_search)
    monkeypatch.setattr(common_handlers, "_replace_status_message", fake_replace)
    monkeypatch.setattr(common_handlers, "track_message_event", fake_track)

    message = Message(
        message_id=1,
        date=datetime.now(),
        chat=Chat(id=10, type="private"),
        from_user=User(id=1, is_bot=False, first_name="Test", language_code="en"),
        text="iphone",
    )
    status_message = Message(
        message_id=2,
        date=datetime.now(),
        chat=Chat(id=10, type="private"),
        text="searching",
    )
    config = Config(bot=BotConfig(token="test"), search_timeout_seconds=0.01)

    await _run_text_search_with_timeout(
        message=message,
        config=config,
        query="iphone",
        status_message=status_message,
    )

    assert events == ["search_timeout"]
    assert replacements == ["Search took too long. Try a simpler query or repeat it later."]


@pytest.mark.asyncio
async def test_text_search_ai_rescue_can_finish_before_timeout(monkeypatch):
    cancelled = False
    delivered: list[str] = []

    async def slow_search(**_kwargs):
        nonlocal cancelled
        try:
            await asyncio.sleep(1)
        except asyncio.CancelledError:
            cancelled = True
            raise

    async def fake_rescue(**_kwargs):
        return common_handlers.TextSearchRescueResult(
            query="Windows 10 лицензионный ключ",
            products=[product(1, "Windows 10 Pro key")],
            sponsored_products=[],
            candidate_offset=1,
        )

    async def fake_deliver(**kwargs):
        delivered.append(kwargs["rescue_result"].query)

    monkeypatch.setattr(common_handlers, "_run_text_search", slow_search)
    monkeypatch.setattr(common_handlers, "_run_text_search_ai_rescue", fake_rescue)
    monkeypatch.setattr(common_handlers, "_deliver_text_search_ai_rescue", fake_deliver)

    message = Message(
        message_id=1,
        date=datetime.now(),
        chat=Chat(id=10, type="private"),
        from_user=User(id=1, is_bot=False, first_name="Test", language_code="ru"),
        text="виндовс 10",
    )
    config = Config(
        bot=BotConfig(token="test"),
        openai_api_key="key",
        search_timeout_seconds=1,
        search_ai_rescue_after_seconds=0.01,
    )

    await _run_text_search_with_timeout(
        message=message,
        config=config,
        query="виндовс 10",
    )

    assert cancelled is True
    assert delivered == ["Windows 10 лицензионный ключ"]


def test_ai_rank_keeps_unranked_products_after_ranked_ids():
    products = [product(1, "A"), product(2, "B"), product(3, "C")]

    ranked = _rank_products_from_ids(products=products, ranked_ids=[3, 2, 999, 2])

    assert [item.id for item in ranked] == [3, 2, 1]


def test_ai_search_expansion_parser_sanitizes_queries_and_prices():
    expansions = _parse_search_expansions(
        [
            {"query": "  овер сайз свитер  ", "min_price": None, "max_price": "300000"},
            {"query": "овер сайз свитер", "min_price": None, "max_price": 400000},
            {"query": "oversize sweater", "min_price": 100000, "max_price": 500000},
            {"query": "", "min_price": None, "max_price": None},
        ],
        max_queries=3,
    )

    assert expansions == [
        SearchExpansion(query="овер сайз свитер", min_price=None, max_price=300000),
        SearchExpansion(query="oversize sweater", min_price=100000, max_price=500000),
    ]


def test_photo_search_output_parser_sanitizes_queries():
    parsed = parse_photo_search_output(
        """
        {
          "query": "  белые кроссовки  ",
          "alternative_queries": [
            "white sneakers",
            "белые кроссовки",
            "",
            "oq krossovka"
          ],
          "confidence": "HIGH",
          "visible_product": "white low-top sneakers",
          "object_type": "кроссовки",
          "brand": "Nike",
          "visible_text": "Air",
          "key_features": ["white", "low top", "lace-up"]
        }
        """
    )

    assert parsed.query == "белые кроссовки"
    assert parsed.alternative_queries == ["white sneakers", "oq krossovka"]
    assert parsed.confidence == "high"
    assert parsed.visible_product == "white low-top sneakers"
    assert parsed.object_type == "кроссовки"
    assert parsed.brand == "Nike"
    assert parsed.visible_text == "Air"
    assert parsed.key_features == ["white", "low top", "lace-up"]


def test_photo_selection_prefers_largest_affordable_photo():
    config = Config(
        bot=BotConfig(token="test"),
        openai_photo_max_pixels=500 * 500,
        openai_photo_max_download_bytes=400_000,
    )
    photos = [
        PhotoSize(file_id="small", file_unique_id="1", width=160, height=160, file_size=20_000),
        PhotoSize(file_id="good", file_unique_id="2", width=480, height=480, file_size=90_000),
        PhotoSize(file_id="large", file_unique_id="3", width=1280, height=1280, file_size=300_000),
    ]

    assert _select_photo_for_vision(photos, config).file_id == "good"


def test_source_product_ids_from_uzum_caption():
    text = (
        "https://uzum.uz/ru/product/steklyannaya-kruzhka-s-kryshkoi-i-"
        "trubochkoi-serdce-ruchka-450-ml-2797446"
    )

    assert _source_product_ids_from_text(text) == ["2797446"]


def test_photo_search_queries_include_visible_text_and_brand():
    parsed = parse_photo_search_output(
        """
        {
          "query": "cerave увлажняющий крем",
          "alternative_queries": ["церава крем", "moisturizing cream"],
          "confidence": "high",
          "visible_product": "white and blue cream jar",
          "object_type": "крем",
          "brand": "CeraVe",
          "visible_text": "Moisturising Cream",
          "key_features": ["белая банка", "синяя этикетка"]
        }
        """
    )

    assert _photo_search_queries(parsed) == [
        "CeraVe крем",
        "CeraVe",
        "cerave увлажняющий крем",
        "церава крем",
        "moisturizing cream",
        "CeraVe Moisturising Cream крем",
    ]


def test_bot_query_requirements_normalize_generic_phone_case_intent():
    assert _query_requirements("чехол на телефон") == [{"чехол"}]
    assert _query_requirements("чехол для смартфона") == [{"чехол"}]
    assert _query_requirements("стикеры на чехол телефона") == [
        {"стикеры"},
        {"чехол"},
        {"телефона"},
    ]


@pytest.mark.parametrize(
    ("query", "requirements"),
    [
        ("стекло на телефон", [{"стекло"}]),
        ("пленка для смартфона", [{"пленка"}]),
        ("зарядка для телефона", [{"зарядка"}]),
        ("кабель для телефона", [{"кабель"}]),
        ("держатель для телефона", [{"держатель"}]),
    ],
)
def test_bot_query_requirements_normalize_generic_phone_accessory_intents(
    query,
    requirements,
):
    assert _query_requirements(query) == requirements


def test_photo_search_queries_prioritize_latin_brand_and_object_type():
    parsed = parse_photo_search_output(
        """
        {
          "query": "Snickers сникерс батончик не тормози",
          "alternative_queries": ["сникерс батончик", "Snickers chocolate bar"],
          "confidence": "high",
          "visible_product": "Snickers chocolate bar",
          "object_type": "батончик",
          "brand": "Snickers",
          "visible_text": "Snickers не тормози",
          "key_features": ["коричневая упаковка", "батончик"]
        }
        """
    )

    assert _photo_search_queries(parsed)[0] == "Snickers батончик"


def test_photo_search_normalizes_snickers_snack_misclassification():
    parsed = parse_photo_search_output(
        """
        {
          "query": "Snickers чипсы Не тормози снеки",
          "alternative_queries": ["Snickers snek", "Snickers snack"],
          "confidence": "high",
          "visible_product": "Snickers snack package",
          "object_type": "чипсы",
          "brand": "Snickers",
          "visible_text": "Snickers Не тормози",
          "key_features": ["коричневая упаковка", "снеки"]
        }
        """
    )

    assert parsed.query == "Snickers шоколадный батончик"
    assert parsed.object_type == "батончик"
    assert parsed.brand == "Snickers"

    queries = _photo_search_queries(parsed)

    assert queries[:5] == [
        "Snickers батончик",
        "Snickers",
        "Snickers шоколадный батончик",
        "Snickers chocolate bar",
        "Snickers snack bar",
    ]
    assert "сникерс батончик" in queries
    assert all("чипс" not in query.casefold() for query in queries)
    assert all("snek" not in query.casefold() for query in queries)


def test_photo_search_queries_add_multilingual_packaged_goods_aliases():
    photo_query = PhotoSearchQuery(
        query="Coca Cola напиток",
        alternative_queries=[],
        confidence="high",
        visible_product="cola bottle",
        object_type="напиток",
        brand="Coca Cola",
        visible_text="Coca Cola",
        key_features=["бутылка"],
    )

    queries = _photo_search_queries(photo_query)

    assert "Coca Cola ichimlik" in queries
    assert "Coca Cola drink" in queries


def test_photo_text_fallback_requires_brand_when_brand_is_visible():
    photo_query = PhotoSearchQuery(
        query="Snickers сникерс батончик",
        alternative_queries=[],
        confidence="high",
        visible_product="Snickers chocolate bar",
        object_type="батончик",
        brand="Snickers",
        visible_text="Snickers",
        key_features=["шоколад"],
    )
    chocolate_bar = product(1, "Батончик шоколадный Toren Choco Dino")
    a4_bar = product(4, "А4 Шоколадный батончик, 40 г")
    shoes = product(2, "Кроссовки мужские сникерсы")
    book = product(3, "Не тормози! Контроль над временем")

    assert _photo_text_fallback_products(
        photo_query=photo_query,
        products=[shoes, book, chocolate_bar, a4_bar],
        limit=10,
    ) == []


def test_photo_exact_candidates_require_visible_brand_and_safe_object_type():
    photo_query = PhotoSearchQuery(
        query="Snickers батончик шоколадный",
        alternative_queries=[],
        confidence="high",
        visible_product="Snickers chocolate bar",
        object_type="батончик",
        brand="Snickers",
        visible_text="Snickers",
        key_features=["шоколад"],
    )
    exact_latin = product(1, "Батончик Snickers, 50 г")
    exact_cyrillic = product(2, "Шоколадный батончик Сникерс, 50 г")
    wrong_brand = product(3, "А4 Шоколадный батончик, 40 г")
    wrong_type = product(4, "Кроссовки мужские сникерсы")

    assert _photo_exact_candidate_products(
        photo_query=photo_query,
        products=[wrong_brand, wrong_type, exact_latin, exact_cyrillic],
    ) == [exact_latin, exact_cyrillic]


def test_photo_substitute_queries_drop_brand_but_keep_safe_object_type():
    photo_query = PhotoSearchQuery(
        query="Snickers сникерс батончик",
        alternative_queries=[],
        confidence="high",
        visible_product="Snickers chocolate bar",
        object_type="батончик",
        brand="Snickers",
        visible_text="Snickers",
        key_features=["шоколад"],
    )

    queries = _photo_substitute_queries(photo_query)

    assert queries[0] == "батончик"
    assert "шоколадный батончик" in queries
    assert all("snickers" not in query.casefold() for query in queries)


def test_photo_substitute_text_fallback_keeps_product_type_without_brand():
    photo_query = PhotoSearchQuery(
        query="Snickers сникерс батончик",
        alternative_queries=[],
        confidence="high",
        visible_product="Snickers chocolate bar",
        object_type="батончик",
        brand="Snickers",
        visible_text="Snickers",
        key_features=["шоколад"],
    )
    chocolate_bar = product(1, "Батончик шоколадный Toren Choco Dino")
    shoes = product(2, "Кроссовки мужские сникерсы")

    assert _photo_text_fallback_products(
        photo_query=photo_query,
        products=[shoes, chocolate_bar],
        limit=10,
        require_brand=False,
    ) == [chocolate_bar]


def test_photo_result_intro_key_distinguishes_substitutes():
    assert _photo_result_intro_key("ai") == "photo_found_intro"
    assert _photo_result_intro_key("text") == "photo_text_fallback_intro"
    assert _photo_result_intro_key("substitute") == "photo_substitute_intro"


def test_photo_text_fallback_allows_unbranded_packaged_goods():
    photo_query = PhotoSearchQuery(
        query="шоколадный батончик",
        alternative_queries=[],
        confidence="medium",
        visible_product="chocolate bar",
        object_type="батончик",
        brand="",
        visible_text="",
        key_features=["шоколад"],
    )
    chocolate_bar = product(1, "Батончик шоколадный Toren Choco Dino")
    shoes = product(2, "Кроссовки мужские сникерсы")

    assert _photo_text_fallback_products(
        photo_query=photo_query,
        products=[shoes, chocolate_bar],
        limit=10,
    ) == [chocolate_bar]


def test_photo_text_fallback_supports_packaged_drinks_but_not_broad_cosmetics():
    drink_query = PhotoSearchQuery(
        query="Coca Cola напиток",
        alternative_queries=[],
        confidence="high",
        visible_product="cola bottle",
        object_type="напиток",
        brand="Coca Cola",
        visible_text="Coca Cola",
        key_features=["бутылка"],
    )
    cream_query = PhotoSearchQuery(
        query="CeraVe крем",
        alternative_queries=[],
        confidence="high",
        visible_product="cream jar",
        object_type="крем",
        brand="CeraVe",
        visible_text="CeraVe",
        key_features=["банка"],
    )
    cola = product(1, "Газированный напиток Cola, 1.5 л")
    cream = product(2, "Увлажняющий крем для лица")

    assert _photo_text_fallback_products(
        photo_query=drink_query,
        products=[cola, cream],
        limit=10,
    ) == [cola]
    assert (
        _photo_text_fallback_products(
            photo_query=cream_query,
            products=[cream],
            limit=10,
        )
        == []
    )


def test_photo_candidate_query_limit_splits_budget():
    config = Config(bot=BotConfig(token="test"), openai_photo_candidate_limit=60)

    assert _photo_candidate_query_limit(config, 1) == 40
    assert _photo_candidate_query_limit(config, 4) == 25


def test_voice_search_availability_requires_key_and_runtime():
    config = Config(bot=BotConfig(token="test"), openai_api_key="key")

    assert _voice_search_available(config) is True
    assert _voice_search_available(Config(bot=BotConfig(token="test"), openai_api_key="")) is False
    assert (
        _voice_search_available(
            Config(
                bot=BotConfig(token="test"),
                openai_api_key="key",
                openai_voice_search_enabled=False,
            )
        )
        is False
    )


def test_config_exposes_voice_defaults():
    config = Config(bot=BotConfig(token="test"))

    assert config.openai_voice_search_enabled is True
    assert config.openai_voice_model == "gpt-4o-mini-transcribe"
    assert config.openai_voice_timeout == 20.0
    assert config.openai_voice_max_download_bytes == 8_000_000
    assert config.openai_voice_max_duration_seconds == 180


def test_config_exposes_rate_limit_defaults():
    config = Config(bot=BotConfig(token="test"))

    assert config.rate_limit_enabled is True
    assert config.rate_limit_admin_bypass is True
    assert config.rate_limit_max_events == 30
    assert config.search_rate_limit_max_events == 12
    assert config.ai_rate_limit_max_events == 12
    assert config.ai_rate_limit_window_seconds == 3600.0
    assert config.search_timeout_seconds == 60.0
    assert config.search_ai_rescue_after_seconds == 30.0
    assert config.marketplace_custom_emoji_ids == {}


def test_consent_versions_match_between_bot_and_server_defaults():
    config = Config(bot=BotConfig(token="test"))

    assert config.consent_version == settings.USER_CONSENT_VERSION


def test_voice_transcription_prompt_uses_language_names_not_codes():
    assert _language_name("uz") == "Uzbek"
    assert _language_name("ru-RU") == "Russian"
    assert _language_name("en_US") == "English"
    assert _language_name("de") == ""

    assert "Uzbek" in _transcription_prompt("uz")
    assert "language code" not in _transcription_prompt("uz").lower()


def test_search_expansion_helpers():
    config = Config(bot=BotConfig(token="test"), openai_api_key="key")

    assert _search_expansion_allowed(config=config, candidate_offset=0) is True
    assert _search_expansion_allowed(config=config, candidate_offset=30) is False
    assert _expansion_filters(SearchExpansion("iphone", min_price=1, max_price=2)) == {
        "min_price": 1,
        "max_price": 2,
    }
    assert [item.id for item in _merge_unique_products([product(1, "A")], [product(1, "A")])] == [1]


def test_ai_fallback_skips_good_local_results():
    products = [
        product(1, "Стильный женский свитер с V-образным вырезом"),
        product(2, "Женский свитер с v вырезом"),
        product(3, "Пуловер с V образным вырезом"),
        product(4, "Джемпер с v-neck"),
        product(5, "Базовый свитер с V-образной горловиной"),
    ]

    assert not _local_results_need_ai("свитер v вырез", products, min_results=5)


def test_ai_fallback_detects_bad_local_results():
    products = [
        product(1, "Свитер с круглой горловиной"),
        product(2, "Кофта без выреза"),
        product(3, "Кардиган на пуговицах"),
        product(4, "Футболка базовая"),
        product(5, "Женский топ"),
    ]

    assert _local_results_need_ai("свитер v вырез", products, min_results=5)


def test_ai_fallback_understands_compression_wear():
    good_products = [
        product(1, "Компрессионный рашгард спортивный"),
        product(2, "Компрессионная футболка для фитнеса"),
        product(3, "Компрессионные тайтсы спортивные"),
        product(4, "Компрессионные шорты мужские"),
        product(5, "Компрессионный рукав для спорта"),
    ]
    bad_products = [
        product(1, "Присадка для увеличения компрессии двигателя"),
        product(2, "Компрессор автомобильный"),
        product(3, "Моторное масло"),
        product(4, "Насос для шин"),
        product(5, "Автохимия"),
    ]

    assert not _local_results_need_ai("компрессионка", good_products, min_results=5)
    assert _local_results_need_ai("компрессионка", bad_products, min_results=5)


def test_quota_error_detection_does_not_confuse_rate_limit():
    assert _is_quota_exhausted_response(
        status=429,
        body='{"error":{"code":"insufficient_quota","message":"quota exceeded"}}',
    )
    assert _is_quota_exhausted_response(
        status=429,
        body=(
            '{"error":{"message":"You exceeded your current quota, '
            'please check your plan and billing details"}}'
        ),
    )
    assert _is_quota_exhausted_response(
        status=403,
        body=(
            '{"error":{"code":"unsupported_country_region_territory",'
            '"message":"Country, region, or territory not supported"}}'
        ),
    )
    assert not _is_quota_exhausted_response(
        status=429,
        body='{"error":{"message":"Rate limit reached for requests"}}',
    )


def test_openai_probe_uses_supported_output_token_minimum():
    assert OPENAI_PROBE_MAX_OUTPUT_TOKENS >= 16


def test_ai_runtime_state_events():
    state = AIRuntimeState()

    state.mark_quota_exhausted("quota")
    state.mark_quota_exhausted("quota again")

    assert not state.ai_allowed()
    assert [event.kind for event in state.consume_events()] == ["disabled"]

    state.mark_available()

    assert state.ai_allowed()
    assert [event.kind for event in state.consume_events()] == ["enabled"]


def test_openai_cost_summary_remaining_budget():
    summary = OpenAICostSummary(today_usd=0.25, month_usd=1.25, monthly_budget_usd=5.0)

    assert summary.remaining_monthly_budget_usd == 3.75
    assert _format_usd(summary.remaining_monthly_budget_usd) == "$3.7500"


def test_openai_cost_bucket_parser_sums_usd_only():
    costs_by_day: dict[int, float] = {}

    _merge_cost_buckets(
        costs_by_day,
        {
            "data": [
                {
                    "start_time": 1,
                    "results": [
                        {"amount": {"value": 0.1, "currency": "usd"}},
                        {"amount": {"value": 0.2, "currency": "USD"}},
                        {"amount": {"value": 5.0, "currency": "eur"}},
                    ],
                },
                {
                    "start_time": 2,
                    "results": [{"amount": {"value": 0.3}}],
                },
            ]
        },
    )

    assert costs_by_day == pytest.approx({1: 0.3, 2: 0.3})


def test_balance_command_admin_check():
    class User:
        id = 976835256

    class Message:
        from_user = User()

    config = Config(bot=BotConfig(token="test"), openai_status_notify_user_id=976835256)

    assert _is_openai_status_admin(Message(), config)
