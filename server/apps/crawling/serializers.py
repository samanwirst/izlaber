from rest_framework import serializers

from apps.crawling.models import CrawlEvent, CrawlRun, SearchBackfillRequest


class CrawlRunSerializer(serializers.ModelSerializer):
    marketplace = serializers.SlugRelatedField(read_only=True, slug_field="code")

    class Meta:
        model = CrawlRun
        fields = "__all__"


class CrawlEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = CrawlEvent
        fields = "__all__"


class CrawlRunStartSerializer(serializers.Serializer):
    marketplace = serializers.CharField(default="uzum")
    run_type = serializers.ChoiceField(choices=CrawlRun.RunType.choices)
    metadata = serializers.JSONField(required=False, default=dict)
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class ProductUpsertBatchSerializer(serializers.Serializer):
    marketplace = serializers.CharField(default="uzum")
    crawl_run_id = serializers.IntegerField(required=False, allow_null=True)
    products = serializers.ListField(child=serializers.DictField(), allow_empty=False)
    create_snapshot = serializers.BooleanField(required=False, default=False)


class ProductHashBatchSerializer(serializers.Serializer):
    marketplace = serializers.CharField(default="uzum")
    source_product_ids = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=False,
    )


class SeenProductBatchSerializer(serializers.Serializer):
    source_product_ids = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=False,
    )


class CrawlRunFinishSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=CrawlRun.Status.choices,
        default=CrawlRun.Status.SUCCESS,
    )
    log_summary = serializers.CharField(required=False, allow_blank=True, default="")
    metadata = serializers.JSONField(required=False, default=dict)
    deactivate_unseen = serializers.BooleanField(required=False, default=False)


class SearchBackfillRequestSerializer(serializers.ModelSerializer):
    marketplace = serializers.SlugRelatedField(read_only=True, slug_field="code")

    class Meta:
        model = SearchBackfillRequest
        fields = "__all__"


class SearchBackfillRequestCreateSerializer(serializers.Serializer):
    marketplace = serializers.CharField(default="uzum")
    query = serializers.CharField(max_length=255)
    source = serializers.CharField(max_length=64, required=False, default="bot_search")
    requested_by_telegram_user_id = serializers.IntegerField(required=False, allow_null=True)
    limit = serializers.IntegerField(required=False, default=30, min_value=1, max_value=100)
    priority = serializers.IntegerField(required=False, default=100, min_value=1, max_value=1000)
    metadata = serializers.JSONField(required=False, default=dict)


class SearchBackfillRequestClaimSerializer(serializers.Serializer):
    marketplace = serializers.CharField(default="uzum")
    worker_id = serializers.CharField(max_length=128)
    stale_after_seconds = serializers.IntegerField(
        required=False,
        default=600,
        min_value=60,
        max_value=3600,
    )


class SearchBackfillRequestFinishSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=SearchBackfillRequest.Status.choices)
    stats = serializers.JSONField(required=False, default=dict)
    error = serializers.CharField(required=False, allow_blank=True, default="")
