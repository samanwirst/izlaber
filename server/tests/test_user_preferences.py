from apps.catalog.models import UserPreference
from rest_framework.test import APIClient


def test_language_preferences_round_trip(settings, db):
    settings.BOT_API_KEY = "bot-key"
    client = APIClient()

    response = client.get("/api/v1/user-preferences/languages/", HTTP_X_INTERNAL_API_KEY="bot-key")
    assert response.status_code == 200
    assert response.data == []

    response = client.post(
        "/api/v1/user-preferences/languages/976835256/",
        {"language_code": "ru"},
        format="json",
        HTTP_X_INTERNAL_API_KEY="bot-key",
    )
    assert response.status_code == 200
    assert response.data["telegram_user_id"] == 976835256
    assert response.data["language_code"] == "ru"

    response = client.get(
        "/api/v1/user-preferences/languages/976835256/",
        HTTP_X_INTERNAL_API_KEY="bot-key",
    )
    assert response.status_code == 200
    assert response.data["language_code"] == "ru"

    assert UserPreference.objects.get(telegram_user_id=976835256).language_code == "ru"
