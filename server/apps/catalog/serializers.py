from rest_framework import serializers

from apps.catalog.models import (
    AnalyticsEvent,
    Category,
    Marketplace,
    Product,
    ProductSnapshot,
    Seller,
    UserConsent,
    UserPreference,
)


class MarketplaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Marketplace
        fields = (
            "id",
            "code",
            "name",
            "base_url",
            "is_active",
            "created_at",
            "updated_at",
        )


class CategorySerializer(serializers.ModelSerializer):
    marketplace = MarketplaceSerializer(read_only=True)

    class Meta:
        model = Category
        fields = (
            "id",
            "marketplace",
            "source_category_id",
            "name",
            "slug",
            "parent",
            "path_text",
            "url",
        )


class SellerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Seller
        fields = ("id", "source_seller_id", "name", "url", "rating")


class ProductSerializer(serializers.ModelSerializer):
    marketplace = MarketplaceSerializer(read_only=True)
    seller = SellerSerializer(read_only=True)
    category = CategorySerializer(read_only=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "marketplace",
            "source_product_id",
            "canonical_url",
            "title",
            "description",
            "brand",
            "seller",
            "category",
            "category_path_text",
            "rating",
            "reviews_count",
            "current_price",
            "old_price",
            "currency",
            "availability",
            "cover_image_url",
            "image_urls",
            "specs",
            "first_seen_at",
            "last_seen_at",
            "unavailable_since",
            "is_active",
            "created_at",
            "updated_at",
        )


class ProductCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = (
            "id",
            "source_product_id",
            "canonical_url",
            "title",
            "brand",
            "category_path_text",
            "rating",
            "reviews_count",
            "current_price",
            "old_price",
            "currency",
            "availability",
            "cover_image_url",
            "last_seen_at",
            "is_active",
        )


class ProductSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductSnapshot
        fields = "__all__"


class UserPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPreference
        fields = ("telegram_user_id", "language_code", "created_at", "updated_at")


class UserConsentSerializer(serializers.ModelSerializer):
    has_active_consent = serializers.SerializerMethodField()

    class Meta:
        model = UserConsent
        fields = (
            "telegram_user_id",
            "consent_version",
            "language_code",
            "source",
            "personal_data_accepted_at",
            "sponsored_ads_accepted_at",
            "declined_at",
            "revoked_at",
            "metadata",
            "has_active_consent",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "personal_data_accepted_at",
            "sponsored_ads_accepted_at",
            "declined_at",
            "revoked_at",
            "created_at",
            "updated_at",
        )

    def get_has_active_consent(self, obj: UserConsent) -> bool:
        version = self.context.get("consent_version")
        return obj.has_active_consent(str(version)) if version else obj.has_active_consent()


class AnalyticsEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalyticsEvent
        fields = (
            "event_id",
            "event_type",
            "source",
            "telegram_user_id",
            "chat_id",
            "message_id",
            "visitor_id",
            "language_code",
            "input_type",
            "query",
            "product",
            "source_product_id",
            "product_position",
            "result_count",
            "request_path",
            "referrer",
            "user_agent",
            "ip_hash",
            "metadata",
            "created_at",
        )
        read_only_fields = ("created_at",)
