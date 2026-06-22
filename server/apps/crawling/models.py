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
