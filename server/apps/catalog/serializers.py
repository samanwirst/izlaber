import re

from rest_framework import serializers

from apps.catalog.models import (
    AnalyticsEvent,
    Category,
    Marketplace,
    Product,
    ProductSnapshot,
    Seller,
    SponsoredCampaign,
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
    marketplace = MarketplaceSerializer(read_only=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "marketplace",
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


class SponsoredCampaignSerializer(serializers.ModelSerializer):
    product = ProductCardSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_active=True),
        source="product",
        write_only=True,
        required=False,
    )
    product_lookup = serializers.CharField(write_only=True, required=False, allow_blank=True)
    impressions = serializers.IntegerField(read_only=True)
    clicks = serializers.IntegerField(read_only=True)
    ctr = serializers.FloatField(read_only=True)
    remaining_total_impressions = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = SponsoredCampaign
        fields = (
            "id",
            "name",
            "advertiser_name",
            "product",
            "product_id",
            "product_lookup",
            "keywords",
            "language_codes",
            "status",
            "priority",
            "starts_at",
            "ends_at",
            "daily_impression_limit",
            "total_impression_limit",
            "notes",
            "metadata",
            "impressions",
            "clicks",
            "ctr",
            "remaining_total_impressions",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "impressions",
            "clicks",
            "ctr",
            "remaining_total_impressions",
        )

    def validate_keywords(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("keywords must be a list of strings.")
        keywords = []
        seen = set()
        for item in value:
            keyword = " ".join(str(item).split())
            key = keyword.casefold()
            if not keyword or key in seen:
                continue
            seen.add(key)
            keywords.append(keyword[:80])
        if not keywords:
            raise serializers.ValidationError("At least one keyword is required.")
        return keywords[:30]

    def validate_language_codes(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("language_codes must be a list of strings.")
        allowed = {"uz", "ru", "en"}
        return [code for code in (str(item).casefold()[:2] for item in value) if code in allowed]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if (
            attrs.get("ends_at")
            and attrs.get("starts_at")
            and attrs["ends_at"] <= attrs["starts_at"]
        ):
            raise serializers.ValidationError({"ends_at": "ends_at must be later than starts_at."})
        if "product" not in attrs:
            product = self._product_from_lookup(self.initial_data.get("product_lookup"))
            if product is not None:
                attrs["product"] = product
        attrs.pop("product_lookup", None)
        if "product" not in attrs and self.instance is None:
            raise serializers.ValidationError({"product_lookup": "Product is required."})
        return attrs

    @staticmethod
    def _product_from_lookup(value) -> Product | None:
        lookup = str(value or "").strip()
        if not lookup:
            return None
        queryset = Product.objects.filter(is_active=True)
        if lookup.isdigit():
            product = queryset.filter(id=int(lookup)).first()
            if product is not None:
                return product
            product = queryset.filter(source_product_id=lookup).first()
            if product is not None:
                return product
        product = queryset.filter(source_product_id=lookup).first()
        if product is not None:
            return product
        numeric_matches = re.findall(r"\d+", lookup)
        for source_product_id in reversed(numeric_matches):
            product = queryset.filter(source_product_id=source_product_id).first()
            if product is not None:
                return product
        return queryset.filter(canonical_url__icontains=lookup).first()
