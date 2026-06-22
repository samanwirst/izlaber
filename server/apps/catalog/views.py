from django.db.models import Case, IntegerField, Q, When
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api_auth.authentication import BotAPIKeyAuthentication
from apps.catalog.models import Category, Marketplace, Product, UserPreference
from apps.catalog.search import query_price_filters, search_product_ids
from apps.catalog.serializers import (
    CategorySerializer,
    MarketplaceSerializer,
    ProductCardSerializer,
    ProductSerializer,
    UserPreferenceSerializer,
)
from apps.catalog.visual import visual_search_product_ids
from apps.catalog.visual_index import index_product_cover_rows, visual_index_queryset


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

    def get_serializer_class(self):
        if self.action in {"list", "visual_search"}:
            return ProductCardSerializer
        return ProductSerializer

    def get_queryset(self):
        queryset = Product.objects.all()
        if self.action != "list":
            queryset = queryset.select_related("marketplace", "seller", "category")
        else:
            queryset = queryset.only(
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
        params = self.request.query_params

        active_only = params.get("active_only", "true").lower()
        if active_only not in {"false", "0", "no"}:
            queryset = queryset.filter(is_active=True)
        if marketplace := params.get("marketplace"):
            queryset = queryset.filter(marketplace__code=marketplace)
        query = params.get("q")
        min_price = params.get("min_price")
        max_price = params.get("max_price")
        if query:
            limit, offset = _pagination_window(params)
            query_min_price, query_max_price = query_price_filters(query)
            min_price = min_price or query_min_price
            max_price = max_price or query_max_price
            product_ids = search_product_ids(
                query,
                marketplace_code=marketplace,
                active_only=active_only not in {"false", "0", "no"},
                limit=limit + offset,
                min_price=min_price,
                max_price=max_price,
            )
            if not product_ids:
                return queryset.none()
            search_order = Case(
                *[When(id=product_id, then=index) for index, product_id in enumerate(product_ids)],
                output_field=IntegerField(),
            )
            queryset = queryset.filter(id__in=product_ids).annotate(search_order=search_order)
        if min_price:
            queryset = queryset.filter(current_price__gte=min_price)
        if max_price:
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

    @action(detail=False, methods=["post"], url_path="visual-search")
    def visual_search(self, request):
        params = request.data
        marketplace = params.get("marketplace") or "uzum"
        active_only = str(params.get("active_only", "true")).lower() not in {"false", "0", "no"}
        limit = min(_positive_int(params.get("limit"), default=20), 100)
        max_distance = min(_positive_int(params.get("max_distance"), default=10), 64)
        product_ids = visual_search_product_ids(
            ahash=params.get("ahash") or "",
            dhash=params.get("dhash") or "",
            marketplace_code=marketplace,
            active_only=active_only,
            limit=limit,
            max_distance=max_distance,
        )
        if not product_ids:
            return Response([])

        search_order = Case(
            *[When(id=product_id, then=index) for index, product_id in enumerate(product_ids)],
            output_field=IntegerField(),
        )
        queryset = (
            Product.objects.only(
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
            .filter(id__in=product_ids)
            .annotate(search_order=search_order)
            .order_by("search_order")
        )
        serializer = ProductCardSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="visual-index")
    def visual_index(self, request):
        params = request.data
        marketplace = params.get("marketplace") or "uzum"
        product_ids = _int_list(params.get("product_ids"))
        source_product_ids = _str_list(params.get("source_product_ids"))
        force = str(params.get("force", "false")).lower() in {"true", "1", "yes"}
        limit = min(_positive_int(params.get("limit"), default=50), 100)
        concurrency = min(_positive_int(params.get("concurrency"), default=8), 32)
        timeout = min(_positive_float(params.get("timeout"), default=12.0), 30.0)

        if not product_ids and not source_product_ids:
            return Response(
                {
                    "processed": 0,
                    "updated": 0,
                    "failed": 0,
                    "detail": "product_ids or source_product_ids is required",
                },
                status=400,
            )

        rows = list(
            visual_index_queryset(
                marketplace_code=marketplace,
                force=force,
                product_ids=product_ids,
                source_product_ids=source_product_ids,
            ).values_list("id", "cover_image_url")[:limit]
        )
        stats = index_product_cover_rows(rows=rows, concurrency=concurrency, timeout=timeout)
        return Response(
            {
                "processed": stats.processed,
                "updated": stats.updated,
                "failed": stats.failed,
            }
        )


class UserPreferenceListView(APIView):
    authentication_classes = (BotAPIKeyAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get(self, _request):
        queryset = UserPreference.objects.all().order_by("telegram_user_id")
        serializer = UserPreferenceSerializer(queryset, many=True)
        return Response(serializer.data)


class UserPreferenceDetailView(APIView):
    authentication_classes = (BotAPIKeyAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get(self, _request, telegram_user_id: str):
        preference = get_object_or_404(UserPreference, telegram_user_id=telegram_user_id)
        serializer = UserPreferenceSerializer(preference)
        return Response(serializer.data)

    def post(self, request, telegram_user_id: str):
        language_code = _normalize_language_code(str(request.data.get("language_code") or ""))
        preference, _ = UserPreference.objects.update_or_create(
            telegram_user_id=telegram_user_id,
            defaults={"language_code": language_code},
        )
        serializer = UserPreferenceSerializer(preference)
        return Response(serializer.data, status=status.HTTP_200_OK)


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


def _positive_float(value, *, default: float) -> float:
    try:
        parsed = float(value) if value is not None else default
    except (TypeError, ValueError):
        return default
    return max(parsed, 0.0)


def _normalize_language_code(language_code: str) -> str:
    base_code = language_code.casefold().replace("_", "-").split("-", maxsplit=1)[0]
    return base_code if base_code in {"uz", "ru", "en"} else "uz"


def _int_list(value) -> list[int]:
    if value is None:
        return []
    if not isinstance(value, list):
        value = [value]
    parsed = []
    for item in value:
        try:
            parsed.append(int(item))
        except (TypeError, ValueError):
            continue
    return parsed


def _str_list(value) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        value = [value]
    return [str(item).strip() for item in value if str(item).strip()]
