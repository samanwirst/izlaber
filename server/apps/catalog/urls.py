from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.catalog.views import (
    CategoryViewSet,
    MarketplaceViewSet,
    ProductViewSet,
    UserPreferenceDetailView,
    UserPreferenceListView,
)

router = DefaultRouter()
router.register("marketplaces", MarketplaceViewSet, basename="marketplace")
router.register("categories", CategoryViewSet, basename="category")
router.register("products", ProductViewSet, basename="product")

urlpatterns = router.urls + [
    path("user-preferences/languages/", UserPreferenceListView.as_view(), name="user-languages"),
    path(
        "user-preferences/languages/<str:telegram_user_id>/",
        UserPreferenceDetailView.as_view(),
        name="user-language-detail",
    ),
]
