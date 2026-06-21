from django.db.models import Case, IntegerField, Q, When
from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from apps.api_auth.authentication import BotAPIKeyAuthentication
from apps.catalog.models import Category, Marketplace, Product
from apps.catalog.search import search_product_ids
from apps.catalog.serializers import CategorySerializer, MarketplaceSerializer, ProductSerializer


class InternalReadOnlyMixin:
    authentication_classes = (BotAPIKeyAuthentication,)
    permission_classes = (IsAuthenticated,)


class MarketplaceViewSet(InternalReadOnlyMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Marketplace.objects.filter(is_active=True)
    serializer_class = MarketplaceSerializer


class CategoryViewSet(InternalReadOnlyMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.select_related("marketplace", "parent").all()
    serializer_class = CategorySerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if marketplace := self.request.query_params.get("marketplace"):
            queryset = queryset.filter(marketplace__code=marketplace)
        return queryset


class ProductViewSet(
    InternalReadOnlyMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = ProductSerializer

    def get_queryset(self):
        queryset = Product.objects.select_related("marketplace", "seller", "category").all()
        params = self.request.query_params

        active_only = params.get("active_only", "true").lower()
        if active_only not in {"false", "0", "no"}:
            queryset = queryset.filter(is_active=True)
        if marketplace := params.get("marketplace"):
            queryset = queryset.filter(marketplace__code=marketplace)
        if query := params.get("q"):
            limit, offset = _pagination_window(params)
            product_ids = search_product_ids(
                query,
                marketplace_code=marketplace,
                active_only=active_only not in {"false", "0", "no"},
                limit=limit + offset,
            )
            if not product_ids:
                return queryset.none()
            search_order = Case(
                *[When(id=product_id, then=index) for index, product_id in enumerate(product_ids)],
                output_field=IntegerField(),
            )
            queryset = queryset.filter(id__in=product_ids).annotate(search_order=search_order)
        if min_price := params.get("min_price"):
            queryset = queryset.filter(current_price__gte=min_price)
        if max_price := params.get("max_price"):
            queryset = queryset.filter(current_price__lte=max_price)
        if category := params.get("category"):
            queryset = queryset.filter(
                Q(category__slug=category)
                | Q(category__source_category_id=category)
                | Q(category_path_text__icontains=category)
            )

        if query:
            return queryset.order_by("search_order")
        return queryset.order_by("-last_seen_at")


def _pagination_window(params) -> tuple[int, int]:
    limit = _positive_int(params.get("limit"), default=20)
    offset = _positive_int(params.get("offset"), default=0)
    return min(limit, 100), offset


def _positive_int(value: str | None, *, default: int) -> int:
    try:
        parsed = int(value) if value is not None else default
    except ValueError:
        return default
    return max(parsed, 0)
