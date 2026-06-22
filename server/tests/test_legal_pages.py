from django.test import Client


def test_legal_pages_are_public_html(db):
    client = Client()

    privacy = client.get("/legal/privacy/")
    sponsored_ads = client.get("/legal/sponsored-ads/")

    assert privacy.status_code == 200
    assert privacy["Content-Type"] == "text/html; charset=utf-8"
    assert privacy["X-Robots-Tag"] == "noindex"
    assert "Izlaber Privacy Policy" in privacy.content.decode()
    assert "/consent" in privacy.content.decode()

    assert sponsored_ads.status_code == 200
    assert sponsored_ads["Content-Type"] == "text/html; charset=utf-8"
    assert "Izlaber Sponsored Advertising" in sponsored_ads.content.decode()
    assert "/consent" in sponsored_ads.content.decode()
