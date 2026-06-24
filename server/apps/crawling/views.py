from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api_auth.authentication import BotAPIKeyAuthentication, ParserAPIKeyAuthentication
from apps.crawling.models import CrawlRun, SearchBackfillRequest
from apps.crawling.serializers import (
    CrawlEventSerializer,
    CrawlRunFinishSerializer,
    CrawlRunSerializer,
    CrawlRunStartSerializer,
    ProductHashBatchSerializer,
    ProductUpsertBatchSerializer,
    SearchBackfillRequestClaimSerializer,
    SearchBackfillRequestCreateSerializer,
    SearchBackfillRequestFinishSerializer,
    SearchBackfillRequestSerializer,
    SeenProductBatchSerializer,
)
from apps.crawling.services import (
    claim_search_backfill_request,
    create_search_backfill_request,
    finish_crawl_run,
    finish_search_backfill_request,
    get_or_create_marketplace,
    get_product_delta_states,
    record_seen_product_ids,
    upsert_products,
)


class InternalAPIView(APIView):
    authentication_classes = (ParserAPIKeyAuthentication,)
    permission_classes = (IsAuthenticated,)


class BotInternalAPIView(APIView):
    authentication_classes = (BotAPIKeyAuthentication,)
    permission_classes = (IsAuthenticated,)


class SearchBackfillRequestCreateView(BotInternalAPIView):
    def post(self, request):
        serializer = SearchBackfillRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        backfill_request = create_search_backfill_request(
            marketplace_code=serializer.validated_data["marketplace"],
            query=serializer.validated_data["query"],
            source=serializer.validated_data.get("source", "bot_search"),
            requested_by_telegram_user_id=serializer.validated_data.get(
                "requested_by_telegram_user_id"
            ),
            limit=serializer.validated_data.get("limit", 30),
            priority=serializer.validated_data.get("priority", 100),
            metadata=serializer.validated_data.get("metadata", {}),
        )
        return Response(SearchBackfillRequestSerializer(backfill_request).data, status=202)


class SearchBackfillRequestDetailView(BotInternalAPIView):
    def get(self, _request, pk: int):
        backfill_request = get_object_or_404(SearchBackfillRequest, pk=pk)
        return Response(SearchBackfillRequestSerializer(backfill_request).data)


class CrawlRunStartView(InternalAPIView):
    def post(self, request):
        serializer = CrawlRunStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        marketplace = get_or_create_marketplace(serializer.validated_data["marketplace"])
        crawl_run = CrawlRun.objects.create(
            marketplace=marketplace,
            run_type=serializer.validated_data["run_type"],
            status=CrawlRun.Status.RUNNING,
            started_at=timezone.now(),
            metadata=serializer.validated_data.get("metadata", {}),
            notes=serializer.validated_data.get("notes", ""),
        )
        return Response(CrawlRunSerializer(crawl_run).data, status=status.HTTP_201_CREATED)


class ProductUpsertBatchView(InternalAPIView):
    def post(self, request):
        serializer = ProductUpsertBatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        crawl_run_id = serializer.validated_data.get("crawl_run_id")
        crawl_run = CrawlRun.objects.filter(id=crawl_run_id).first() if crawl_run_id else None
        stats = upsert_products(
            marketplace_code=serializer.validated_data["marketplace"],
            products=serializer.validated_data["products"],
            crawl_run=crawl_run,
            create_snapshot=serializer.validated_data["create_snapshot"],
        )
        return Response(
            {
                "created_count": stats.created,
                "updated_count": stats.updated,
                "unchanged_count": stats.unchanged,
                "reactivated_count": stats.reactivated,
            }
        )


class ProductHashBatchView(InternalAPIView):
    def post(self, request):
        serializer = ProductHashBatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        products = get_product_delta_states(
            marketplace_code=serializer.validated_data["marketplace"],
            source_product_ids=serializer.validated_data["source_product_ids"],
        )
        hashes = {
            source_product_id: product["content_hash"]
            for source_product_id, product in products.items()
        }
        return Response({"hashes": hashes, "products": products})


class SeenProductBatchView(InternalAPIView):
    def post(self, request, pk: int):
        serializer = SeenProductBatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        crawl_run = CrawlRun.objects.get(pk=pk)
        seen_count = record_seen_product_ids(
            crawl_run=crawl_run,
            source_product_ids=serializer.validated_data["source_product_ids"],
        )
        return Response({"seen_count": seen_count})


class CrawlRunFinishView(InternalAPIView):
    def post(self, request, pk: int):
        serializer = CrawlRunFinishSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        crawl_run = CrawlRun.objects.get(pk=pk)
        crawl_run = finish_crawl_run(
            crawl_run=crawl_run,
            status=serializer.validated_data["status"],
            log_summary=serializer.validated_data.get("log_summary", ""),
            metadata=serializer.validated_data.get("metadata", {}),
            deactivate_unseen=serializer.validated_data.get("deactivate_unseen", False),
        )
        return Response(CrawlRunSerializer(crawl_run).data)


class CrawlEventCreateView(InternalAPIView):
    def post(self, request):
        serializer = CrawlEventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = serializer.save()
        return Response(CrawlEventSerializer(event).data, status=status.HTTP_201_CREATED)


class SearchBackfillRequestClaimView(InternalAPIView):
    def post(self, request):
        serializer = SearchBackfillRequestClaimSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        backfill_request = claim_search_backfill_request(
            marketplace_code=serializer.validated_data["marketplace"],
            worker_id=serializer.validated_data["worker_id"],
            stale_after_seconds=serializer.validated_data.get("stale_after_seconds", 600),
        )
        if backfill_request is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(SearchBackfillRequestSerializer(backfill_request).data)


class SearchBackfillRequestFinishView(InternalAPIView):
    def post(self, request, pk: int):
        serializer = SearchBackfillRequestFinishSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        backfill_request = finish_search_backfill_request(
            request_id=pk,
            status=serializer.validated_data["status"],
            stats=serializer.validated_data.get("stats", {}),
            error=serializer.validated_data.get("error", ""),
        )
        return Response(SearchBackfillRequestSerializer(backfill_request).data)
