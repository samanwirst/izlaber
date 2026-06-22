from apps.catalog.models import AnalyticsEvent, Product, UserConsent
from apps.crawling.services import upsert_products
from django.utils import timezone
from rest_framework.test import APIClient


def product_payload(source_product_id="p1", content_hash="hash-1"):
    return {
        "source_product_id": source_product_id,
        "canonical_url": f"https://uzum.uz/ru/product/test-{source_product_id}",
        "title": f"Test product {source_product_id}",
        "current_price": "1000.00",
        "old_price": None,
        "currency": "UZS",
        "availability": "available",
        "image_urls": ["https://images.example/test.jpg"],
        "specs": {},
        "raw_data": {"id": source_product_id},
        "content_hash": content_hash,
    }


def test_analytics_summary_returns_dashboard_aggregates(settings, db):
    settings.BOT_API_KEY = "bot-key"
    settings.USER_CONSENT_VERSION = "test-v1"
    upsert_products(marketplace_code="uzum", products=[product_payload()])
    product = Product.objects.get()
    now = timezone.now()
    UserConsent.objects.create(
        telegram_user_id=1,
        consent_version="test-v1",
        language_code="ru",
        personal_data_accepted_at=now,
        sponsored_ads_accepted_at=now,
    )
    UserConsent.objects.create(
        telegram_user_id=2,
        consent_version="test-v1",
        language_code="en",
        declined_at=now,
    )

    AnalyticsEvent.objects.create(
        event_type="search",
        telegram_user_id=1,
        language_code="ru",
        input_type="text",
        query="iphone",
    )
    AnalyticsEvent.objects.create(
        event_type="search_no_results",
        telegram_user_id=1,
        language_code="ru",
        input_type="text",
        query="iphone",
        result_count=0,
    )
    AnalyticsEvent.objects.create(
        event_type="view_item_list",
        telegram_user_id=1,
        language_code="ru",
        input_type="product_card",
        query="iphone",
        product=product,
        result_count=5,
    )
    AnalyticsEvent.objects.create(
        event_type="select_item",
        telegram_user_id=1,
        language_code="ru",
        input_type="click",
        query="iphone",
        product=product,
    )

    client = APIClient()
    response = client.get(
        "/api/v1/analytics/summary/",
        {"days": 7},
        HTTP_X_INTERNAL_API_KEY="bot-key",
    )

    assert response.status_code == 200
    assert response.data["period"]["days"] == 7
    assert response.data["kpis"] == {
        "users": 1,
        "searches": 1,
        "no_results": 1,
        "impressions": 1,
        "clicks": 1,
        "ctr": 100.0,
        "no_result_rate": 100.0,
        "active_consents": 1,
    }
    assert response.data["consents"] == {
        "active": 1,
        "declined": 1,
        "revoked": 0,
        "total": 2,
    }
    assert response.data["top_queries"][0]["query"] == "iphone"
    assert response.data["top_queries"][0]["searches"] == 2
    assert response.data["top_products"][0]["title"] == product.title
    assert response.data["top_products"][0]["ctr"] == 100.0
    assert response.data["languages"][0] == {"name": "ru", "value": 4}
    assert response.data["input_types"][0]["name"] == "text"
    assert len(response.data["time_series"]) == 7


def test_analytics_summary_requires_internal_key(settings, db):
    settings.BOT_API_KEY = "bot-key"

    response = APIClient().get("/api/v1/analytics/summary/")

    assert response.status_code == 403
