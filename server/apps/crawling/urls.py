from django.urls import path

from apps.crawling.views import (
    CrawlEventCreateView,
    CrawlRunFinishView,
    CrawlRunStartView,
    ProductHashBatchView,
    ProductUpsertBatchView,
    SeenProductBatchView,
)

urlpatterns = [
    path("crawl-runs/start/", CrawlRunStartView.as_view(), name="crawl-run-start"),
    path(
        "crawl-runs/<int:pk>/seen-products/",
        SeenProductBatchView.as_view(),
        name="crawl-run-seen-products",
    ),
    path("products/upsert-batch/", ProductUpsertBatchView.as_view(), name="product-upsert-batch"),
    path("products/hash-batch/", ProductHashBatchView.as_view(), name="product-hash-batch"),
    path("crawl-runs/<int:pk>/finish/", CrawlRunFinishView.as_view(), name="crawl-run-finish"),
    path("crawl-events/", CrawlEventCreateView.as_view(), name="crawl-event-create"),
]
