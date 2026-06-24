from django.db import models


class CrawlRun(models.Model):
    class RunType(models.TextChoices):
        FULL = "full", "Full"
        INCREMENTAL = "incremental", "Incremental"
        RESUME = "resume", "Resume"
        TEST = "test", "Test"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        PARTIAL = "partial", "Partial"

    marketplace = models.ForeignKey("catalog.Marketplace", on_delete=models.CASCADE)
    run_type = models.CharField(max_length=32, choices=RunType.choices)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PENDING)
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(blank=True, null=True)
    discovered_count = models.PositiveIntegerField(default=0)
    fetched_count = models.PositiveIntegerField(default=0)
    created_count = models.PositiveIntegerField(default=0)
    updated_count = models.PositiveIntegerField(default=0)
    unchanged_count = models.PositiveIntegerField(default=0)
    deactivated_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)
    log_summary = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-started_at",)
        indexes = [
            models.Index(fields=["marketplace", "status"]),
            models.Index(fields=["run_type", "started_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.marketplace.code} {self.run_type} {self.status}"


class CrawlEvent(models.Model):
    class Level(models.TextChoices):
        INFO = "info", "Info"
        WARNING = "warning", "Warning"
        ERROR = "error", "Error"

    crawl_run = models.ForeignKey(CrawlRun, on_delete=models.CASCADE, related_name="events")
    level = models.CharField(max_length=16, choices=Level.choices, default=Level.INFO)
    event_type = models.CharField(max_length=128)
    message = models.TextField()
    url = models.URLField(max_length=1024, blank=True, null=True)
    source_product_id = models.CharField(max_length=255, blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["crawl_run", "level"]),
            models.Index(fields=["event_type"]),
            models.Index(fields=["source_product_id"]),
        ]


class CrawlRunSeenProduct(models.Model):
    crawl_run = models.ForeignKey(CrawlRun, on_delete=models.CASCADE, related_name="seen_products")
    source_product_id = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["crawl_run", "source_product_id"],
                name="crawling_cr_crawl_r_d92e5c_idx",
            ),
            models.Index(
                fields=["source_product_id"],
                name="crawling_cr_source__5ba149_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["crawl_run", "source_product_id"],
                name="unique_crawl_run_seen_product",
            )
        ]


class SearchBackfillRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        SUCCESS = "success", "Success"
        PARTIAL = "partial", "Partial"
        FAILED = "failed", "Failed"

    marketplace = models.ForeignKey("catalog.Marketplace", on_delete=models.CASCADE)
    query = models.CharField(max_length=255)
    normalized_query = models.CharField(max_length=255)
    source = models.CharField(max_length=64, default="bot_search")
    requested_by_telegram_user_id = models.BigIntegerField(blank=True, null=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PENDING)
    priority = models.PositiveSmallIntegerField(default=100)
    attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=3)
    limit = models.PositiveSmallIntegerField(default=30)
    worker_id = models.CharField(max_length=128, blank=True)
    claimed_at = models.DateTimeField(blank=True, null=True)
    finished_at = models.DateTimeField(blank=True, null=True)
    discovered_count = models.PositiveIntegerField(default=0)
    changed_count = models.PositiveIntegerField(default=0)
    created_count = models.PositiveIntegerField(default=0)
    updated_count = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("priority", "created_at")
        indexes = [
            models.Index(fields=["marketplace", "status", "priority", "created_at"]),
            models.Index(fields=["marketplace", "normalized_query", "status"]),
            models.Index(fields=["status", "claimed_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.marketplace.code} {self.status} {self.query}"
