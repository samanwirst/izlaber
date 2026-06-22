from rest_framework import serializers

from apps.catalog.models import Category, Marketplace, Product, ProductSnapshot, Seller


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
