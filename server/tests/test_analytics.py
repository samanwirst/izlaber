from uuid import UUID

from apps.catalog.models import AnalyticsEvent, Product
from apps.crawling.services import upsert_products
from rest_framework.test import APIClient


def product_payload(source_product_id="p1", content_hash="hash-1"):
    return {
        "source_product_id": source_product_id,
        "canonical_url": f"https://uzum.uz/ru/product/test-{source_product_id}",
        "title": "Test product",
        "current_price": "1000.00",
        "old_price": None,
        "currency": "UZS",
        "availability": "available",
        "image_urls": ["https://images.uzum.uz/test/t_product_540_high.jpg"],
        "specs": {"color": "black"},
        "raw_data": {"id": source_product_id},
        "content_hash": content_hash,
    }


def test_bot_can_store_analytics_event(settings, db):
    settings.BOT_API_KEY = "bot-key"
    upsert_products(marketplace_code="uzum", products=[product_payload()])
    product = Product.objects.get()

    client = APIClient()
    response = client.post(
        "/api/v1/analytics/events/",
        {
            "event_type": "search",
            "telegram_user_id": 976835256,
            "chat_id": 10,
            "message_id": 20,
            "language_code": "ru",
            "input_type": "text",
            "query": "iphone",
            "product": product.id,
            "result_count": 1,
            "metadata": {"item_ids": [product.id]},
        },
        format="json",
        HTTP_X_INTERNAL_API_KEY="bot-key",
    )

    assert response.status_code == 201
    event = AnalyticsEvent.objects.get()
    assert event.event_type == "search"
    assert event.telegram_user_id == 976835256
    assert event.product == product
    assert event.metadata == {"item_ids": [product.id]}


def test_product_click_redirect_stores_click_with_cookie_context(settings, db):
    settings.ANALYTICS_COOKIE_ENABLED = True
    settings.ANALYTICS_COOKIE_NAME = "izlaber_test_cid"
    settings.ANALYTICS_COOKIE_MAX_AGE_SECONDS = 3600
    settings.ANALYTICS_HASH_IP = True
    settings.ANALYTICS_IP_HASH_SALT = "test-salt"
    upsert_products(marketplace_code="uzum", products=[product_payload()])
    product = Product.objects.get()
    context_event = AnalyticsEvent.objects.create(
        event_type="view_item_list",
        source=AnalyticsEvent.Source.BOT,
        telegram_user_id=42,
        chat_id=100,
        message_id=200,
        language_code="ru",
        input_type="product_card",
        query="test query",
        product=product,
        source_product_id=product.source_product_id,
        product_position=3,
        result_count=5,
    )

    client = APIClient()
    response = client.get(
        f"/api/v1/redirect/products/{product.id}/",
        {"ctx": str(context_event.event_id)},
        HTTP_USER_AGENT="Mozilla/5.0 Test",
        HTTP_REFERER="https://t.me/izlaber_bot",
        REMOTE_ADDR="127.0.0.1",
    )

    assert response.status_code == 302
    assert response["Location"] == product.canonical_url
    assert response["Referrer-Policy"] == "no-referrer"
    assert settings.ANALYTICS_COOKIE_NAME in response.cookies

    click = AnalyticsEvent.objects.get(event_type="select_item")
    assert click.telegram_user_id == 42
    assert click.chat_id == 100
    assert click.query == "test query"
    assert click.product == product
    assert click.source_product_id == product.source_product_id
    assert click.product_position == 3
    assert click.visitor_id == response.cookies[settings.ANALYTICS_COOKIE_NAME].value
    assert len(click.ip_hash) == 64
    assert click.metadata["context_event_id"] == str(context_event.event_id)
    assert UUID(click.metadata["context_event_id"]) == context_event.event_id
