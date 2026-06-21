from rest_framework.routers import DefaultRouter

from apps.catalog.views import CategoryViewSet, MarketplaceViewSet, ProductViewSet

router = DefaultRouter()
router.register("marketplaces", MarketplaceViewSet, basename="marketplace")
router.register("categories", CategoryViewSet, basename="category")
router.register("products", ProductViewSet, basename="product")

urlpatterns = router.urls
