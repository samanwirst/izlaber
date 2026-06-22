import pytest

from bot.config import BotConfig, Config
from bot.handlers.admin import _format_usd, _is_openai_status_admin
from bot.handlers.common import (
    _expansion_filters,
    _local_results_need_ai,
    _merge_unique_products,
    _search_expansion_allowed,
    _strip_bot_username,
)
from bot.services.ai_reranker import (
    OPENAI_PROBE_MAX_OUTPUT_TOKENS,
    SearchExpansion,
    _is_quota_exhausted_response,
    _parse_search_expansions,
    _rank_products_from_ids,
    rerank_products,
)
from bot.services.ai_runtime import AIRuntimeState
from bot.services.api_client import ProductDTO
from bot.services.openai_billing import OpenAICostSummary, _merge_cost_buckets
from bot.services.search_state import SearchStateStore


def product(product_id: int, title: str) -> ProductDTO:
    return ProductDTO(
        id=product_id,
        title=title,
        canonical_url=f"https://uzum.uz/ru/product/test-{product_id}",
        cover_image_url=None,
        brand=None,
        current_price=None,
        old_price=None,
        currency="UZS",
        rating=None,
        reviews_count=None,
        category_path_text=None,
    )


@pytest.mark.asyncio
async def test_ai_rerank_falls_back_without_api_key():
    config = Config(bot=BotConfig(token="test"), openai_api_key="")
    products = [product(1, "A"), product(2, "B")]

    assert await rerank_products(query="phone", products=products, config=config) == products


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


def test_guest_query_strips_bot_username():
    assert _strip_bot_username("@MarketBot iphone 15", "marketbot") == "iphone 15"
    assert _strip_bot_username("найди @MarketBot ноутбук", "marketbot") == "найди ноутбук"
    assert _strip_bot_username("чехол @otherbot", "marketbot") == "чехол @otherbot"


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


def test_search_expansion_helpers():
    config = Config(bot=BotConfig(token="test"), openai_api_key="key")

    assert _search_expansion_allowed(config=config, candidate_offset=0) is True
    assert _search_expansion_allowed(config=config, candidate_offset=30) is False
    assert _expansion_filters(SearchExpansion("iphone", min_price=1, max_price=2)) == {
        "min_price": 1,
        "max_price": 2,
    }
    assert [item.id for item in _merge_unique_products([product(1, "A")], [product(1, "A")])] == [
        1
    ]


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
