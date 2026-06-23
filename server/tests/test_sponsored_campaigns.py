from apps.catalog.models import AnalyticsEvent, Product, SponsoredCampaign
from apps.crawling.services import upsert_products
from rest_framework.test import APIClient


def product_payload(source_product_id="p1", title="Iphone case", content_hash="hash-1"):
    return {
        "source_product_id": source_product_id,
        "canonical_url": f"https://example.com/product/{source_product_id}",
        "title": title,
        "current_price": "1000.00",
        "old_price": None,
        "currency": "UZS",
        "availability": "available",
        "image_urls": ["https://images.example/test.jpg"],
        "specs": {},
        "raw_data": {"id": source_product_id},
        "content_hash": content_hash,
    }


def test_sponsored_campaign_api_creates_and_matches_placement(settings, db):
    settings.BOT_API_KEY = "bot-key"
    upsert_products(marketplace_code="uzum", products=[product_payload()])

    client = APIClient()
    response = client.post(
        "/api/v1/sponsored-campaigns/",
        {
            "name": "Phone accessories boost",
            "advertiser_name": "Test Seller",
            "product_lookup": "p1",
            "keywords": ["iphone case", "чехол iphone"],
            "language_codes": ["ru"],
            "status": "active",
            "priority": 150,
        },
        format="json",
        HTTP_X_INTERNAL_API_KEY="bot-key",
    )

    assert response.status_code == 201
    assert response.data["product"]["source_product_id"] == "p1"
    assert response.data["impressions"] == 0

    placement = client.get(
        "/api/v1/sponsored-placements/",
        {"q": "нужен чехол iphone", "language_code": "ru", "limit": 1},
        HTTP_X_INTERNAL_API_KEY="bot-key",
    )

    assert placement.status_code == 200
    assert placement.data[0]["title"] == "Iphone case"
    assert placement.data[0]["is_sponsored"] is True
    assert placement.data[0]["sponsored_advertiser_name"] == "Test Seller"

    wrong_language = client.get(
        "/api/v1/sponsored-placements/",
        {"q": "iphone case", "language_code": "en", "limit": 1},
        HTTP_X_INTERNAL_API_KEY="bot-key",
    )

    assert wrong_language.status_code == 200
    assert wrong_language.data == []


def test_sponsored_placement_respects_impression_limit(settings, db):
    settings.BOT_API_KEY = "bot-key"
    upsert_products(marketplace_code="uzum", products=[product_payload()])
    product = Product.objects.get()
    campaign = SponsoredCampaign.objects.create(
        name="Limited boost",
        advertiser_name="Test Seller",
        product=product,
        keywords=["iphone"],
        status=SponsoredCampaign.Status.ACTIVE,
        total_impression_limit=1,
    )
    AnalyticsEvent.objects.create(
        event_type="sponsored_impression",
        product=product,
        metadata={"sponsored_campaign_id": str(campaign.id)},
    )

    response = APIClient().get(
        "/api/v1/sponsored-placements/",
        {"q": "iphone", "language_code": "ru", "limit": 1},
        HTTP_X_INTERNAL_API_KEY="bot-key",
    )

    assert response.status_code == 200
    assert response.data == []


def test_sponsored_redirect_records_sponsored_click(settings, db):
    settings.BOT_API_KEY = "bot-key"
    upsert_products(marketplace_code="uzum", products=[product_payload()])
    product = Product.objects.get()
    campaign = SponsoredCampaign.objects.create(
        name="Click boost",
        advertiser_name="Test Seller",
        product=product,
        keywords=["iphone"],
        status=SponsoredCampaign.Status.ACTIVE,
    )
    context_event = AnalyticsEvent.objects.create(
        event_type="sponsored_impression",
        source=AnalyticsEvent.Source.BOT,
        telegram_user_id=42,
        product=product,
        metadata={
            "sponsored_campaign_id": str(campaign.id),
            "sponsored_campaign_name": campaign.name,
            "sponsored_advertiser_name": campaign.advertiser_name,
        },
    )

    response = APIClient().get(
        f"/api/v1/redirect/products/{product.id}/",
        {"ctx": str(context_event.event_id)},
    )

    assert response.status_code == 302
    click = AnalyticsEvent.objects.get(event_type="sponsored_click")
    assert click.product == product
    assert click.metadata["is_sponsored"] is True
    assert click.metadata["sponsored_campaign_id"] == str(campaign.id)
