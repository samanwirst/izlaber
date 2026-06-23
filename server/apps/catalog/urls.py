from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.catalog.views import (
    AnalyticsEventCreateView,
    AnalyticsSummaryView,
    CategoryViewSet,
    MarketplaceViewSet,
    ProductClickRedirectView,
    ProductViewSet,
    SponsoredCampaignDetailView,
    SponsoredCampaignListView,
    SponsoredPlacementListView,
    UserConsentDetailView,
    UserConsentListView,
    UserPreferenceDetailView,
    UserPreferenceListView,
)

router = DefaultRouter()
router.register("marketplaces", MarketplaceViewSet, basename="marketplace")
router.register("categories", CategoryViewSet, basename="category")
router.register("products", ProductViewSet, basename="product")

urlpatterns = router.urls + [
    path("analytics/events/", AnalyticsEventCreateView.as_view(), name="analytics-event-create"),
    path("analytics/summary/", AnalyticsSummaryView.as_view(), name="analytics-summary"),
    path(
        "sponsored-campaigns/",
        SponsoredCampaignListView.as_view(),
        name="sponsored-campaigns",
    ),
    path(
        "sponsored-campaigns/<int:campaign_id>/",
        SponsoredCampaignDetailView.as_view(),
        name="sponsored-campaign-detail",
    ),
    path(
        "sponsored-placements/",
        SponsoredPlacementListView.as_view(),
        name="sponsored-placements",
    ),
    path("user-consents/", UserConsentListView.as_view(), name="user-consents"),
    path(
        "user-consents/<str:telegram_user_id>/",
        UserConsentDetailView.as_view(),
        name="user-consent-detail",
    ),
    path("user-preferences/languages/", UserPreferenceListView.as_view(), name="user-languages"),
    path(
        "user-preferences/languages/<str:telegram_user_id>/",
        UserPreferenceDetailView.as_view(),
        name="user-language-detail",
    ),
    path(
        "redirect/products/<int:product_id>/",
        ProductClickRedirectView.as_view(),
        name="product-click-redirect",
    ),
]
