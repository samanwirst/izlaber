from django.contrib import admin

from apps.catalog.models import (
    AnalyticsEvent,
    Category,
    Marketplace,
    Product,
    ProductSnapshot,
    Seller,
    SponsoredCampaign,
    UserConsent,
    UserConsentEvent,
)


@admin.register(Marketplace)
class MarketplaceAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "base_url", "is_active", "updated_at")
    search_fields = ("code", "name")
    list_filter = ("is_active",)


@admin.register(Seller)
class SellerAdmin(admin.ModelAdmin):
    list_display = ("name", "marketplace", "source_seller_id", "rating")
    search_fields = ("name", "source_seller_id")
    list_filter = ("marketplace",)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "marketplace", "source_category_id", "parent")
    search_fields = ("name", "path_text", "source_category_id")
    list_filter = ("marketplace",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "marketplace",
        "source_product_id",
        "current_price",
        "availability",
        "cover_image_url",
        "is_active",
        "last_seen_at",
    )
    search_fields = ("title", "source_product_id", "canonical_url")
    list_filter = ("marketplace", "availability", "is_active")
    readonly_fields = ("first_seen_at", "last_seen_at", "created_at", "updated_at")


@admin.register(ProductSnapshot)
class ProductSnapshotAdmin(admin.ModelAdmin):
    list_display = ("product", "price", "availability", "content_hash", "created_at")
    search_fields = ("product__title", "content_hash")


class UserConsentEventInline(admin.TabularInline):
    model = UserConsentEvent
    extra = 0
    can_delete = False
    show_change_link = True
    fields = ("action", "consent_version", "language_code", "source", "occurred_at")
    readonly_fields = fields

    def has_add_permission(self, _request, _obj=None):
        return False


@admin.register(UserConsent)
class UserConsentAdmin(admin.ModelAdmin):
    list_display = (
        "telegram_user_id",
        "consent_version",
        "language_code",
        "personal_data_accepted_at",
        "sponsored_ads_accepted_at",
        "declined_at",
        "revoked_at",
        "updated_at",
    )
    search_fields = ("=telegram_user_id", "consent_version")
    list_filter = ("consent_version", "language_code", "source", "revoked_at")
    readonly_fields = ("created_at", "updated_at")
    inlines = (UserConsentEventInline,)


@admin.register(UserConsentEvent)
class UserConsentEventAdmin(admin.ModelAdmin):
    list_display = (
        "telegram_user_id",
        "action",
        "consent_version",
        "language_code",
        "source",
        "occurred_at",
    )
    search_fields = ("=telegram_user_id", "consent_version")
    list_filter = ("action", "consent_version", "language_code", "source")
    readonly_fields = (
        "consent",
        "telegram_user_id",
        "action",
        "consent_version",
        "language_code",
        "source",
        "occurred_at",
        "metadata",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, _request):
        return False


@admin.register(SponsoredCampaign)
class SponsoredCampaignAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "advertiser_name",
        "product",
        "status",
        "priority",
        "starts_at",
        "ends_at",
        "updated_at",
    )
    search_fields = (
        "name",
        "advertiser_name",
        "product__title",
        "product__source_product_id",
    )
    list_filter = ("status", "starts_at", "ends_at")
    autocomplete_fields = ("product",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(AnalyticsEvent)
class AnalyticsEventAdmin(admin.ModelAdmin):
    list_display = (
        "event_type",
        "source",
        "telegram_user_id",
        "visitor_id",
        "product",
        "result_count",
        "created_at",
    )
    search_fields = ("event_type", "query", "source_product_id", "visitor_id")
    list_filter = ("event_type", "source", "created_at")
    readonly_fields = ("event_id", "created_at")
