import uuid

from django.db import models
from django.utils import timezone


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Marketplace(TimestampedModel):
    code = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    base_url = models.URLField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("code",)

    def __str__(self) -> str:
        return self.name


class Seller(TimestampedModel):
    marketplace = models.ForeignKey(Marketplace, on_delete=models.CASCADE, related_name="sellers")
    source_seller_id = models.CharField(max_length=255, blank=True, null=True)
    name = models.CharField(max_length=255)
    url = models.URLField(blank=True, null=True)
    rating = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)
    raw_data = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [models.Index(fields=["marketplace", "source_seller_id"])]
        constraints = [
            models.UniqueConstraint(
                fields=["marketplace", "source_seller_id"],
                name="unique_marketplace_seller_source_id",
                condition=models.Q(source_seller_id__isnull=False),
            )
        ]

    def __str__(self) -> str:
        return self.name


class Category(TimestampedModel):
    marketplace = models.ForeignKey(
        Marketplace,
        on_delete=models.CASCADE,
        related_name="categories",
    )
    source_category_id = models.CharField(max_length=255, blank=True, null=True)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, blank=True, null=True)
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, blank=True, null=True)
    path_text = models.TextField(blank=True)
    url = models.URLField(blank=True, null=True)
    raw_data = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name_plural = "categories"
        indexes = [
            models.Index(fields=["marketplace", "source_category_id"]),
            models.Index(fields=["slug"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["marketplace", "source_category_id"],
                name="unique_marketplace_category_source_id",
                condition=models.Q(source_category_id__isnull=False),
            )
        ]

    def __str__(self) -> str:
        return self.path_text or self.name


class Product(TimestampedModel):
    class Availability(models.TextChoices):
        AVAILABLE = "available", "Available"
        UNAVAILABLE = "unavailable", "Unavailable"
        UNKNOWN = "unknown", "Unknown"

    marketplace = models.ForeignKey(Marketplace, on_delete=models.CASCADE, related_name="products")
    source_product_id = models.CharField(max_length=255)
    canonical_url = models.URLField(max_length=1024)
    title = models.CharField(max_length=512)
    description = models.TextField(blank=True, null=True)
    brand = models.CharField(max_length=255, blank=True, null=True)
    seller = models.ForeignKey(Seller, on_delete=models.SET_NULL, blank=True, null=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, blank=True, null=True)
    category_path_text = models.TextField(blank=True, null=True)
    rating = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)
    reviews_count = models.PositiveIntegerField(blank=True, null=True)
    current_price = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    old_price = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    currency = models.CharField(max_length=8, default="UZS")
    availability = models.CharField(
        max_length=32,
        choices=Availability.choices,
        default=Availability.UNKNOWN,
        db_index=True,
    )
    cover_image_url = models.URLField(max_length=1024, blank=True, null=True)
    cover_image_ahash = models.CharField(max_length=16, blank=True, null=True, db_index=True)
    cover_image_dhash = models.CharField(max_length=16, blank=True, null=True, db_index=True)
    cover_image_fingerprint_url = models.URLField(max_length=1024, blank=True, null=True)
    cover_image_fingerprint_at = models.DateTimeField(blank=True, null=True)
    image_urls = models.JSONField(default=list, blank=True)
    specs = models.JSONField(default=dict, blank=True)
    raw_data = models.JSONField(default=dict, blank=True)
    search_text = models.TextField(blank=True, default="")
    content_hash = models.CharField(max_length=64)
    first_seen_at = models.DateTimeField(default=timezone.now)
    last_seen_at = models.DateTimeField(default=timezone.now)
    unavailable_since = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("-last_seen_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["marketplace", "source_product_id"],
                name="unique_marketplace_product_source_id",
            )
        ]
        indexes = [
            models.Index(fields=["marketplace", "source_product_id"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["current_price"]),
            models.Index(fields=["title"]),
            models.Index(fields=["updated_at"]),
            models.Index(fields=["last_seen_at"]),
            models.Index(
                fields=["cover_image_ahash", "cover_image_dhash"],
                name="catalog_pro_cover_hash_idx",
            ),
            models.Index(
                fields=["marketplace", "is_active", "current_price"],
                name="catalog_pro_mkt_act_price_idx",
            ),
        ]

    def __str__(self) -> str:
        return self.title


class ProductSnapshot(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="snapshots")
    crawl_run = models.ForeignKey(
        "crawling.CrawlRun",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="product_snapshots",
    )
    price = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    old_price = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    availability = models.CharField(max_length=32)
    rating = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)
    reviews_count = models.PositiveIntegerField(blank=True, null=True)
    content_hash = models.CharField(max_length=64)
    raw_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["product", "created_at"])]


class ProductSearchTerm(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="search_terms")
    marketplace_code = models.SlugField(max_length=50)
    term = models.CharField(max_length=64)
    weight = models.PositiveSmallIntegerField(default=1)
    product_is_active = models.BooleanField(default=True)
    product_rating = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)
    product_reviews_count = models.PositiveIntegerField(blank=True, null=True)
    product_last_seen_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["term", "marketplace_code", "product_is_active", "weight"],
                name="catalog_pro_term_7035d6_idx",
            ),
            models.Index(
                fields=["product", "term"],
                name="catalog_pro_product_dd6b80_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "term"],
                name="unique_product_search_term",
            )
        ]


class UserPreference(TimestampedModel):
    telegram_user_id = models.BigIntegerField(unique=True, db_index=True)
    language_code = models.SlugField(max_length=8, default="uz")

    class Meta:
        ordering = ("telegram_user_id",)

    def __str__(self) -> str:
        return f"{self.telegram_user_id}: {self.language_code}"


class UserConsent(TimestampedModel):
    class Source(models.TextChoices):
        BOT = "bot", "Bot"

    telegram_user_id = models.BigIntegerField(unique=True, db_index=True)
    consent_version = models.SlugField(max_length=64)
    language_code = models.SlugField(max_length=8, default="uz")
    source = models.CharField(max_length=32, choices=Source.choices, default=Source.BOT)
    personal_data_accepted_at = models.DateTimeField(blank=True, null=True)
    sponsored_ads_accepted_at = models.DateTimeField(blank=True, null=True)
    declined_at = models.DateTimeField(blank=True, null=True)
    revoked_at = models.DateTimeField(blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("telegram_user_id",)
        indexes = [
            models.Index(fields=["consent_version", "revoked_at"]),
            models.Index(fields=["personal_data_accepted_at", "sponsored_ads_accepted_at"]),
        ]

    def has_active_consent(self, consent_version: str | None = None) -> bool:
        if consent_version and self.consent_version != consent_version:
            return False
        return bool(
            self.personal_data_accepted_at
            and self.sponsored_ads_accepted_at
            and self.revoked_at is None
        )

    def __str__(self) -> str:
        state = "active" if self.has_active_consent() else "inactive"
        return f"{self.telegram_user_id}: {self.consent_version} ({state})"


class UserConsentEvent(TimestampedModel):
    class Action(models.TextChoices):
        ACCEPT = "accept", "Accept"
        DECLINE = "decline", "Decline"
        REVOKE = "revoke", "Revoke"

    consent = models.ForeignKey(
        UserConsent,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="events",
    )
    telegram_user_id = models.BigIntegerField(db_index=True)
    action = models.CharField(max_length=16, choices=Action.choices, db_index=True)
    consent_version = models.SlugField(max_length=64)
    language_code = models.SlugField(max_length=8, default="uz")
    source = models.CharField(
        max_length=32,
        choices=UserConsent.Source.choices,
        default=UserConsent.Source.BOT,
    )
    occurred_at = models.DateTimeField(db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-occurred_at", "-id")
        indexes = [
            models.Index(fields=["telegram_user_id", "-occurred_at"]),
            models.Index(fields=["consent_version", "action"]),
        ]

    def __str__(self) -> str:
        return f"{self.telegram_user_id}: {self.action} {self.consent_version}"


class SponsoredCampaign(TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        FINISHED = "finished", "Finished"

    name = models.CharField(max_length=255)
    advertiser_name = models.CharField(max_length=255)
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="sponsored_campaigns",
    )
    keywords = models.JSONField(default=list, blank=True)
    language_codes = models.JSONField(default=list, blank=True)
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    priority = models.PositiveSmallIntegerField(default=100)
    starts_at = models.DateTimeField(blank=True, null=True)
    ends_at = models.DateTimeField(blank=True, null=True)
    daily_impression_limit = models.PositiveIntegerField(blank=True, null=True)
    total_impression_limit = models.PositiveIntegerField(blank=True, null=True)
    notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("status", "-priority", "-updated_at")
        indexes = [
            models.Index(fields=["status", "starts_at", "ends_at"]),
            models.Index(fields=["product", "status"]),
            models.Index(fields=["priority"]),
        ]

    def is_active_now(self, now=None) -> bool:
        now = now or timezone.now()
        if self.status != self.Status.ACTIVE:
            return False
        if self.starts_at and self.starts_at > now:
            return False
        return not (self.ends_at and self.ends_at <= now)

    def __str__(self) -> str:
        return f"{self.name} ({self.advertiser_name})"


class AnalyticsEvent(models.Model):
    class Source(models.TextChoices):
        BOT = "bot", "Bot"
        REDIRECT = "redirect", "Redirect"
        SERVER = "server", "Server"

    event_id = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    event_type = models.SlugField(max_length=64, db_index=True)
    source = models.CharField(max_length=32, choices=Source.choices, default=Source.BOT)
    telegram_user_id = models.BigIntegerField(blank=True, null=True, db_index=True)
    chat_id = models.BigIntegerField(blank=True, null=True, db_index=True)
    message_id = models.BigIntegerField(blank=True, null=True)
    visitor_id = models.CharField(max_length=64, blank=True, db_index=True)
    language_code = models.SlugField(max_length=8, blank=True)
    input_type = models.SlugField(max_length=32, blank=True)
    query = models.TextField(blank=True)
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="analytics_events",
    )
    source_product_id = models.CharField(max_length=255, blank=True, null=True)
    product_position = models.PositiveIntegerField(blank=True, null=True)
    result_count = models.PositiveIntegerField(blank=True, null=True)
    request_path = models.TextField(blank=True)
    referrer = models.TextField(blank=True)
    user_agent = models.TextField(blank=True)
    ip_hash = models.CharField(max_length=64, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["event_type", "created_at"]),
            models.Index(fields=["telegram_user_id", "created_at"]),
            models.Index(fields=["visitor_id", "created_at"]),
            models.Index(fields=["product", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.event_type} {self.event_id}"
