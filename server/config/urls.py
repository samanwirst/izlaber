from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from config.legal import privacy_policy, sponsored_ads_policy


def healthz(_request):
    return HttpResponse("ok")


urlpatterns = [
    path("healthz/", healthz, name="healthz"),
    path("legal/privacy/", privacy_policy, name="privacy-policy"),
    path("legal/sponsored-ads/", sponsored_ads_policy, name="sponsored-ads-policy"),
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/v1/", include("apps.catalog.urls")),
    path("api/internal/", include("apps.crawling.urls")),
]
