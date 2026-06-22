from apps.catalog.models import UserConsent
from rest_framework.test import APIClient


def test_user_consent_accept_list_and_revoke(settings, db):
    settings.BOT_API_KEY = "bot-key"
    settings.USER_CONSENT_VERSION = "test-v1"
    client = APIClient()

    response = client.get(
        "/api/v1/user-consents/",
        {"active_only": "true", "version": "test-v1"},
        HTTP_X_INTERNAL_API_KEY="bot-key",
    )
    assert response.status_code == 200
    assert response.data == []

    response = client.post(
        "/api/v1/user-consents/976835256/",
        {
            "action": "accept",
            "consent_version": "test-v1",
            "language_code": "ru",
        },
        format="json",
        HTTP_X_INTERNAL_API_KEY="bot-key",
    )
    assert response.status_code == 200
    assert response.data["has_active_consent"] is True
    assert response.data["language_code"] == "ru"
    assert response.data["personal_data_accepted_at"]
    assert response.data["sponsored_ads_accepted_at"]

    response = client.get(
        "/api/v1/user-consents/",
        {"active_only": "true", "version": "test-v1"},
        HTTP_X_INTERNAL_API_KEY="bot-key",
    )
    assert response.status_code == 200
    assert [row["telegram_user_id"] for row in response.data] == [976835256]

    response = client.get(
        "/api/v1/user-consents/",
        {"active_only": "true", "version": "test-v2"},
        HTTP_X_INTERNAL_API_KEY="bot-key",
    )
    assert response.status_code == 200
    assert response.data == []

    response = client.post(
        "/api/v1/user-consents/976835256/",
        {"action": "revoke", "consent_version": "test-v1", "language_code": "ru"},
        format="json",
        HTTP_X_INTERNAL_API_KEY="bot-key",
    )
    assert response.status_code == 200
    assert response.data["has_active_consent"] is False
    assert response.data["revoked_at"]

    response = client.get(
        "/api/v1/user-consents/",
        {"active_only": "true", "version": "test-v1"},
        HTTP_X_INTERNAL_API_KEY="bot-key",
    )
    assert response.status_code == 200
    assert response.data == []


def test_user_consent_decline_records_without_activation(settings, db):
    settings.BOT_API_KEY = "bot-key"
    client = APIClient()

    response = client.post(
        "/api/v1/user-consents/42/",
        {
            "action": "decline",
            "consent_version": "test-v1",
            "language_code": "en-US",
        },
        format="json",
        HTTP_X_INTERNAL_API_KEY="bot-key",
    )

    assert response.status_code == 200
    assert response.data["has_active_consent"] is False
    assert response.data["language_code"] == "en"
    assert response.data["declined_at"]
    consent = UserConsent.objects.get(telegram_user_id=42)
    assert consent.personal_data_accepted_at is None
    assert consent.sponsored_ads_accepted_at is None


def test_user_consent_rejects_unknown_action(settings, db):
    settings.BOT_API_KEY = "bot-key"
    client = APIClient()

    response = client.post(
        "/api/v1/user-consents/42/",
        {"action": "unknown"},
        format="json",
        HTTP_X_INTERNAL_API_KEY="bot-key",
    )

    assert response.status_code == 400
