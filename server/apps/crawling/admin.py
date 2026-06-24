from django.contrib import admin

from apps.crawling.models import CrawlEvent, CrawlRun, SearchBackfillRequest


@admin.register(CrawlRun)
class CrawlRunAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "marketplace",
        "run_type",
        "status",
        "started_at",
        "finished_at",
        "created_count",
        "updated_count",
        "unchanged_count",
        "deactivated_count",
        "failed_count",
    )
    list_filter = ("marketplace", "run_type", "status")
    readonly_fields = ("started_at", "finished_at")


@admin.register(CrawlEvent)
class CrawlEventAdmin(admin.ModelAdmin):
    list_display = ("crawl_run", "level", "event_type", "source_product_id", "created_at")
    search_fields = ("message", "url", "source_product_id")
    list_filter = ("level", "event_type")


@admin.register(SearchBackfillRequest)
class SearchBackfillRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "marketplace",
        "query",
        "source",
        "status",
        "attempts",
        "limit",
        "created_count",
        "updated_count",
        "created_at",
        "finished_at",
    )
    search_fields = ("query", "normalized_query", "last_error", "worker_id")
    list_filter = ("marketplace", "source", "status")
    readonly_fields = ("created_at", "updated_at", "claimed_at", "finished_at")
