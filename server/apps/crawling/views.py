from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api_auth.authentication import ParserAPIKeyAuthentication
from apps.crawling.models import CrawlRun
from apps.crawling.serializers import (
    CrawlEventSerializer,
    CrawlRunFinishSerializer,
    CrawlRunSerializer,
    CrawlRunStartSerializer,
    ProductHashBatchSerializer,
    ProductUpsertBatchSerializer,
    SeenProductBatchSerializer,
)
from apps.crawling.services import (
    finish_crawl_run,
    get_or_create_marketplace,
    get_product_delta_states,
    record_seen_product_ids,
    upsert_products,
)


class InternalAPIView(APIView):
    authentication_classes = (ParserAPIKeyAuthentication,)
    permission_classes = (IsAuthenticated,)


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
