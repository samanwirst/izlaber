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
