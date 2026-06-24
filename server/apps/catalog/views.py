import hashlib
import re
import uuid
from datetime import timedelta

from django.conf import settings
from django.db.models import Case, Count, IntegerField, Q, When
from django.db.models.functions import TruncDate
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api_auth.authentication import BotAPIKeyAuthentication
from apps.catalog.models import (
    AnalyticsEvent,
    Category,
    Marketplace,
    Product,
    SponsoredCampaign,
    UserConsent,
    UserPreference,
)
from apps.catalog.search import query_price_filters, search_product_ids
from apps.catalog.serializers import (
    AnalyticsEventSerializer,
    CategorySerializer,
    MarketplaceSerializer,
    ProductCardSerializer,
    ProductSerializer,
    SponsoredCampaignSerializer,
    UserConsentSerializer,
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
            queryset = queryset.select_related("marketplace").only(
                "id",
                "marketplace__id",
                "marketplace__code",
                "marketplace__name",
                "marketplace__base_url",
                "marketplace__is_active",
                "marketplace__created_at",
                "marketplace__updated_at",
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
        marketplace = params.get("marketplace") or None
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
            Product.objects.select_related("marketplace")
            .only(
                "id",
                "marketplace__id",
                "marketplace__code",
                "marketplace__name",
                "marketplace__base_url",
                "marketplace__is_active",
                "marketplace__created_at",
                "marketplace__updated_at",
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


class UserConsentListView(APIView):
    authentication_classes = (BotAPIKeyAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        version = _consent_version(request.query_params.get("version"))
        queryset = UserConsent.objects.all().order_by("telegram_user_id")
        active_only = str(request.query_params.get("active_only", "false")).lower()
        if active_only in {"true", "1", "yes"}:
            queryset = queryset.filter(
                consent_version=version,
                personal_data_accepted_at__isnull=False,
                sponsored_ads_accepted_at__isnull=False,
                revoked_at__isnull=True,
            )
        serializer = UserConsentSerializer(
            queryset,
            many=True,
            context={"consent_version": version},
        )
        return Response(serializer.data)


class UserConsentDetailView(APIView):
    authentication_classes = (BotAPIKeyAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get(self, request, telegram_user_id: str):
        consent = get_object_or_404(UserConsent, telegram_user_id=telegram_user_id)
        version = _consent_version(request.query_params.get("version"))
        serializer = UserConsentSerializer(consent, context={"consent_version": version})
        return Response(serializer.data)

    def post(self, request, telegram_user_id: str):
        try:
            user_id = int(telegram_user_id)
        except ValueError:
            return Response({"detail": "telegram_user_id must be an integer"}, status=400)

        action = str(request.data.get("action") or "").strip().casefold()
        if action not in {"accept", "decline", "revoke"}:
            return Response({"detail": "action must be accept, decline, or revoke"}, status=400)

        version = _consent_version(request.data.get("consent_version"))
        language_code = _normalize_language_code(str(request.data.get("language_code") or ""))
        now = timezone.now()
        metadata = request.data.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        consent, _ = UserConsent.objects.get_or_create(
            telegram_user_id=user_id,
            defaults={
                "consent_version": version,
                "language_code": language_code,
                "metadata": metadata,
            },
        )
        consent.consent_version = version
        consent.language_code = language_code
        consent.source = UserConsent.Source.BOT
        consent.metadata = metadata

        if action == "accept":
            consent.personal_data_accepted_at = now
            consent.sponsored_ads_accepted_at = now
            consent.declined_at = None
            consent.revoked_at = None
        elif action == "decline":
            consent.personal_data_accepted_at = None
            consent.sponsored_ads_accepted_at = None
            consent.declined_at = now
            consent.revoked_at = None
        else:
            consent.declined_at = None
            consent.revoked_at = now

        consent.save()
        serializer = UserConsentSerializer(consent, context={"consent_version": version})
        return Response(serializer.data, status=status.HTTP_200_OK)


class SponsoredCampaignListView(APIView):
    authentication_classes = (BotAPIKeyAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        queryset = SponsoredCampaign.objects.select_related("product").order_by(
            "status",
            "-priority",
            "-updated_at",
        )
        if status_value := request.query_params.get("status"):
            queryset = queryset.filter(status=status_value)
        campaigns = _with_sponsored_stats(list(queryset[:200]))
        serializer = SponsoredCampaignSerializer(campaigns, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = SponsoredCampaignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        campaign = serializer.save()
        campaign = _with_sponsored_stats([campaign])[0]
        return Response(SponsoredCampaignSerializer(campaign).data, status=status.HTTP_201_CREATED)


class SponsoredCampaignDetailView(APIView):
    authentication_classes = (BotAPIKeyAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get(self, _request, campaign_id: int):
        campaign = get_object_or_404(
            SponsoredCampaign.objects.select_related("product"),
            pk=campaign_id,
        )
        campaign = _with_sponsored_stats([campaign])[0]
        return Response(SponsoredCampaignSerializer(campaign).data)

    def patch(self, request, campaign_id: int):
        campaign = get_object_or_404(SponsoredCampaign, pk=campaign_id)
        serializer = SponsoredCampaignSerializer(campaign, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        campaign = serializer.save()
        campaign = _with_sponsored_stats([campaign])[0]
        return Response(SponsoredCampaignSerializer(campaign).data)


class SponsoredPlacementListView(APIView):
    authentication_classes = (BotAPIKeyAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        query = " ".join(str(request.query_params.get("q") or "").split())
        if not query:
            return Response([])
        language_code = _normalize_language_code(
            str(request.query_params.get("language_code") or "")
        )
        limit = min(_positive_int(request.query_params.get("limit"), default=1), 5)
        if limit <= 0:
            return Response([])

        now = timezone.now()
        queryset = (
            SponsoredCampaign.objects.select_related("product")
            .filter(status=SponsoredCampaign.Status.ACTIVE, product__is_active=True)
            .filter(Q(starts_at__isnull=True) | Q(starts_at__lte=now))
            .filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now))
            .order_by("-priority", "-updated_at")
        )
        campaigns: list[SponsoredCampaign] = []
        for campaign in queryset[:200]:
            if not _campaign_allows_language(campaign, language_code):
                continue
            if not _campaign_matches_query(campaign, query):
                continue
            if _campaign_limits_exhausted(campaign, now=now):
                continue
            campaigns.append(campaign)
            if len(campaigns) >= limit:
                break

        return Response([_sponsored_placement_payload(campaign) for campaign in campaigns])


class AnalyticsEventCreateView(APIView):
    authentication_classes = (BotAPIKeyAuthentication,)
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        event_id = request.data.get("event_id")
        if event_id:
            existing = AnalyticsEvent.objects.filter(event_id=event_id).first()
            if existing is not None:
                return Response(AnalyticsEventSerializer(existing).data, status=status.HTTP_200_OK)

        serializer = AnalyticsEventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = serializer.save(source=serializer.validated_data.get("source") or "bot")
        return Response(AnalyticsEventSerializer(event).data, status=status.HTTP_201_CREATED)


class AnalyticsSummaryView(APIView):
    authentication_classes = (BotAPIKeyAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        days = min(_positive_int(request.query_params.get("days"), default=30) or 30, 180)
        end_at = timezone.now()
        start_at = end_at - timedelta(days=days - 1)
        start_date = start_at.date()
        queryset = AnalyticsEvent.objects.filter(created_at__gte=start_at, created_at__lte=end_at)

        searches = queryset.filter(event_type="search").count()
        no_results = queryset.filter(event_type="search_no_results").count()
        impressions = queryset.filter(event_type="view_item_list").count()
        clicks = queryset.filter(event_type="select_item").count()
        sponsored_impressions = queryset.filter(event_type="sponsored_impression").count()
        sponsored_clicks = queryset.filter(event_type="sponsored_click").count()
        users = (
            queryset.exclude(telegram_user_id__isnull=True)
            .values("telegram_user_id")
            .distinct()
            .count()
        )

        return Response(
            {
                "period": {
                    "days": days,
                    "from": start_at.isoformat(),
                    "to": end_at.isoformat(),
                },
                "kpis": {
                    "users": users,
                    "searches": searches,
                    "no_results": no_results,
                    "impressions": impressions,
                    "clicks": clicks,
                    "ctr": _rate(clicks, impressions),
                    "sponsored_impressions": sponsored_impressions,
                    "sponsored_clicks": sponsored_clicks,
                    "sponsored_ctr": _rate(sponsored_clicks, sponsored_impressions),
                    "active_sponsored_campaigns": _active_sponsored_campaign_count(),
                    "no_result_rate": _rate(no_results, searches),
                    "active_consents": _active_consent_count(),
                },
                "time_series": _analytics_time_series(queryset, start_date=start_date, days=days),
                "event_mix": _event_mix(queryset),
                "top_queries": _top_queries(queryset),
                "top_products": _top_products(queryset),
                "languages": _dimension_counts(queryset, "language_code"),
                "input_types": _dimension_counts(queryset, "input_type"),
                "consents": _consent_summary(),
                "generated_at": end_at.isoformat(),
            }
        )


class ProductClickRedirectView(APIView):
    authentication_classes = ()
    permission_classes = ()

    def get(self, request, product_id: int):
        product = get_object_or_404(
            Product.objects.only("id", "source_product_id", "canonical_url"),
            pk=product_id,
        )
        context_event = _context_analytics_event(request.GET.get("ctx"))
        visitor_id = _request_visitor_id(request)
        metadata = {
            "context_event_id": str(context_event.event_id) if context_event else "",
            "target_url": product.canonical_url,
        }
        event_type = "select_item"
        if context_event and context_event.event_type == "sponsored_impression":
            event_type = "sponsored_click"
            metadata["is_sponsored"] = True
            for key in (
                "sponsored_campaign_id",
                "sponsored_campaign_name",
                "sponsored_advertiser_name",
            ):
                if key in context_event.metadata:
                    metadata[key] = context_event.metadata[key]
        if raw_context := request.GET.get("ctx"):
            metadata["raw_context_event_id"] = raw_context

        AnalyticsEvent.objects.create(
            event_type=event_type,
            source=AnalyticsEvent.Source.REDIRECT,
            telegram_user_id=context_event.telegram_user_id if context_event else None,
            chat_id=context_event.chat_id if context_event else None,
            message_id=context_event.message_id if context_event else None,
            visitor_id=visitor_id,
            language_code=context_event.language_code if context_event else "",
            input_type="click",
            query=context_event.query if context_event else "",
            product=product,
            source_product_id=product.source_product_id,
            product_position=context_event.product_position if context_event else None,
            result_count=context_event.result_count if context_event else None,
            request_path=request.get_full_path(),
            referrer=request.META.get("HTTP_REFERER", ""),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
            ip_hash=_request_ip_hash(request),
            metadata=metadata,
        )

        response = HttpResponseRedirect(product.canonical_url)
        response["Referrer-Policy"] = "no-referrer"
        response["X-Robots-Tag"] = "noindex, nofollow"
        should_set_cookie = (
            settings.ANALYTICS_COOKIE_ENABLED
            and settings.ANALYTICS_COOKIE_NAME not in request.COOKIES
        )
        if should_set_cookie:
            response.set_cookie(
                settings.ANALYTICS_COOKIE_NAME,
                visitor_id,
                max_age=settings.ANALYTICS_COOKIE_MAX_AGE_SECONDS,
                httponly=True,
                secure=not settings.DEBUG,
                samesite="Lax",
            )
        return response


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


def _consent_version(value: str | None) -> str:
    version = str(value or "").strip()
    return version or settings.USER_CONSENT_VERSION


def _active_consent_count() -> int:
    return UserConsent.objects.filter(
        consent_version=settings.USER_CONSENT_VERSION,
        personal_data_accepted_at__isnull=False,
        sponsored_ads_accepted_at__isnull=False,
        revoked_at__isnull=True,
    ).count()


def _consent_summary() -> dict[str, int]:
    return {
        "active": _active_consent_count(),
        "declined": UserConsent.objects.filter(declined_at__isnull=False).count(),
        "revoked": UserConsent.objects.filter(revoked_at__isnull=False).count(),
        "total": UserConsent.objects.count(),
    }


def _active_sponsored_campaign_count() -> int:
    now = timezone.now()
    return (
        SponsoredCampaign.objects.filter(
            status=SponsoredCampaign.Status.ACTIVE,
            product__is_active=True,
        )
        .filter(Q(starts_at__isnull=True) | Q(starts_at__lte=now))
        .filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now))
        .count()
    )


def _with_sponsored_stats(campaigns: list[SponsoredCampaign]) -> list[SponsoredCampaign]:
    for campaign in campaigns:
        impressions = _campaign_event_count(campaign, "sponsored_impression")
        clicks = _campaign_event_count(campaign, "sponsored_click")
        campaign.impressions = impressions
        campaign.clicks = clicks
        campaign.ctr = _rate(clicks, impressions)
        campaign.remaining_total_impressions = (
            None
            if campaign.total_impression_limit is None
            else max(campaign.total_impression_limit - impressions, 0)
        )
    return campaigns


def _campaign_allows_language(campaign: SponsoredCampaign, language_code: str) -> bool:
    language_codes = campaign.language_codes if isinstance(campaign.language_codes, list) else []
    if not language_codes:
        return True
    return language_code in {str(code).casefold()[:2] for code in language_codes}


def _campaign_matches_query(campaign: SponsoredCampaign, query: str) -> bool:
    query_text = query.casefold()
    query_tokens = set(_query_tokens(query_text))
    keywords = campaign.keywords if isinstance(campaign.keywords, list) else []
    for keyword in keywords:
        keyword_text = " ".join(str(keyword).casefold().split())
        if not keyword_text:
            continue
        keyword_tokens = set(_query_tokens(keyword_text))
        if keyword_text in query_text or keyword_tokens <= query_tokens:
            return True
    return False


def _campaign_limits_exhausted(campaign: SponsoredCampaign, *, now) -> bool:
    if campaign.total_impression_limit is not None:
        total = _campaign_event_count(campaign, "sponsored_impression")
        if total >= campaign.total_impression_limit:
            return True
    if campaign.daily_impression_limit is not None:
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        daily = _campaign_event_count(
            campaign,
            "sponsored_impression",
            created_at_gte=day_start,
        )
        if daily >= campaign.daily_impression_limit:
            return True
    return False


def _campaign_event_count(
    campaign: SponsoredCampaign,
    event_type: str,
    *,
    created_at_gte=None,
) -> int:
    queryset = AnalyticsEvent.objects.filter(
        event_type=event_type,
        metadata__sponsored_campaign_id=str(campaign.id),
    )
    if created_at_gte is not None:
        queryset = queryset.filter(created_at__gte=created_at_gte)
    return queryset.count()


def _sponsored_placement_payload(campaign: SponsoredCampaign) -> dict:
    payload = ProductCardSerializer(campaign.product).data
    payload.update(
        {
            "sponsored_campaign_id": campaign.id,
            "sponsored_campaign_name": campaign.name,
            "sponsored_advertiser_name": campaign.advertiser_name,
            "is_sponsored": True,
        }
    )
    return payload


def _query_tokens(value: str) -> list[str]:
    return re.findall(r"[0-9a-zа-яё]+", value.casefold().replace("ё", "е"))


def _analytics_time_series(queryset, *, start_date, days: int) -> list[dict[str, int | str]]:
    rows = (
        queryset.annotate(day=TruncDate("created_at"))
        .values("day", "event_type")
        .annotate(count=Count("id"))
        .order_by("day")
    )
    counts = {(row["day"], row["event_type"]): row["count"] for row in rows}
    user_rows = (
        queryset.exclude(telegram_user_id__isnull=True)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(users=Count("telegram_user_id", distinct=True))
        .order_by("day")
    )
    users_by_day = {row["day"]: row["users"] for row in user_rows}

    return [
        {
            "date": (start_date + timedelta(days=offset)).isoformat(),
            "users": users_by_day.get(start_date + timedelta(days=offset), 0),
            "searches": counts.get((start_date + timedelta(days=offset), "search"), 0),
            "no_results": counts.get((start_date + timedelta(days=offset), "search_no_results"), 0),
            "impressions": counts.get((start_date + timedelta(days=offset), "view_item_list"), 0),
            "clicks": counts.get((start_date + timedelta(days=offset), "select_item"), 0),
            "sponsored_impressions": counts.get(
                (start_date + timedelta(days=offset), "sponsored_impression"), 0
            ),
            "sponsored_clicks": counts.get(
                (start_date + timedelta(days=offset), "sponsored_click"), 0
            ),
        }
        for offset in range(days)
    ]


def _event_mix(queryset) -> list[dict[str, int | str]]:
    return [
        {"name": row["event_type"], "value": row["count"]}
        for row in queryset.values("event_type").annotate(count=Count("id")).order_by("-count")
    ]


def _top_queries(queryset) -> list[dict[str, int | str | float]]:
    rows = (
        queryset.filter(event_type__in={"search", "search_no_results"})
        .exclude(query="")
        .values("query")
        .annotate(
            searches=Count("id"),
            no_results=Count("id", filter=Q(event_type="search_no_results")),
        )
        .order_by("-searches", "query")[:12]
    )
    return [
        {
            "query": row["query"],
            "searches": row["searches"],
            "no_results": row["no_results"],
            "no_result_rate": _rate(row["no_results"], row["searches"]),
        }
        for row in rows
    ]


def _top_products(queryset) -> list[dict[str, int | str | float]]:
    rows = (
        queryset.filter(product__isnull=False, event_type__in={"view_item_list", "select_item"})
        .values(
            "product_id",
            "product__title",
            "product__canonical_url",
            "product__cover_image_url",
        )
        .annotate(
            impressions=Count("id", filter=Q(event_type="view_item_list")),
            clicks=Count("id", filter=Q(event_type="select_item")),
        )
        .order_by("-clicks", "-impressions", "product__title")[:12]
    )
    return [
        {
            "id": row["product_id"],
            "title": row["product__title"] or "",
            "url": row["product__canonical_url"] or "",
            "cover_image_url": row["product__cover_image_url"] or "",
            "impressions": row["impressions"],
            "clicks": row["clicks"],
            "ctr": _rate(row["clicks"], row["impressions"]),
        }
        for row in rows
    ]


def _dimension_counts(queryset, field_name: str) -> list[dict[str, int | str]]:
    return [
        {"name": row[field_name] or "unknown", "value": row["count"]}
        for row in queryset.exclude(**{field_name: ""})
        .values(field_name)
        .annotate(count=Count("id"))
        .order_by("-count", field_name)
    ]


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100, 2)


def _context_analytics_event(value: str | None) -> AnalyticsEvent | None:
    if not value:
        return None
    try:
        event_id = uuid.UUID(str(value))
    except ValueError:
        return None
    return AnalyticsEvent.objects.filter(event_id=event_id).first()


def _request_visitor_id(request) -> str:
    if not settings.ANALYTICS_COOKIE_ENABLED:
        return ""
    visitor_id = request.COOKIES.get(settings.ANALYTICS_COOKIE_NAME, "").strip()
    if visitor_id:
        return visitor_id[:64]
    return uuid.uuid4().hex


def _request_ip_hash(request) -> str:
    if not settings.ANALYTICS_HASH_IP:
        return ""
    raw_ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",", maxsplit=1)[0].strip()
    raw_ip = raw_ip or request.META.get("REMOTE_ADDR", "")
    if not raw_ip:
        return ""
    value = f"{settings.ANALYTICS_IP_HASH_SALT}:{raw_ip}".encode()
    return hashlib.sha256(value).hexdigest()


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
