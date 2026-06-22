from __future__ import annotations

import asyncio
from dataclasses import dataclass

from aiohttp import ClientError, ClientSession, ClientTimeout
from django.db.models import F, Q, QuerySet
from django.utils import timezone

from apps.catalog.models import Product
from apps.catalog.visual import ImageFingerprintError, image_fingerprint


@dataclass(frozen=True, slots=True)
class FingerprintResult:
    product_id: int
    cover_image_url: str
    ahash: str
    dhash: str


@dataclass(frozen=True, slots=True)
class VisualIndexStats:
    processed: int = 0
    updated: int = 0
    failed: int = 0


def visual_index_queryset(
    *,
    marketplace_code: str = "uzum",
    force: bool = False,
    product_ids: list[int] | None = None,
    source_product_ids: list[str] | None = None,
) -> QuerySet[Product]:
    queryset = Product.objects.filter(
        marketplace__code=marketplace_code,
        cover_image_url__isnull=False,
    ).exclude(cover_image_url="")
    if product_ids:
        queryset = queryset.filter(id__in=product_ids)
    if source_product_ids:
        queryset = queryset.filter(source_product_id__in=source_product_ids)
    if not force:
        queryset = queryset.filter(
            Q(cover_image_ahash__isnull=True)
            | Q(cover_image_dhash__isnull=True)
            | Q(cover_image_fingerprint_url__isnull=True)
            | ~Q(cover_image_fingerprint_url=F("cover_image_url"))
        )
    return queryset.order_by("id")


def index_product_cover_rows(
    *,
    rows: list[tuple[int, str]],
    concurrency: int = 16,
    timeout: float = 12.0,
) -> VisualIndexStats:
    if not rows:
        return VisualIndexStats()
    results = asyncio.run(
        _fingerprint_batch(
            rows=rows,
            concurrency=max(1, concurrency),
            timeout=max(1.0, timeout),
        )
    )
    updated = bulk_update_visual_fingerprints(results)
    return VisualIndexStats(
        processed=len(rows),
        updated=updated,
        failed=len(rows) - len(results),
    )


async def _fingerprint_batch(
    *,
    rows: list[tuple[int, str]],
    concurrency: int,
    timeout: float,
) -> list[FingerprintResult]:
    semaphore = asyncio.Semaphore(concurrency)
    timeout_config = ClientTimeout(total=timeout)
    async with ClientSession(timeout=timeout_config) as session:
        tasks = [
            _fingerprint_one(
                session=session,
                semaphore=semaphore,
                product_id=product_id,
                cover_image_url=cover_image_url,
            )
            for product_id, cover_image_url in rows
        ]
        results = await asyncio.gather(*tasks)
    return [result for result in results if result is not None]


async def _fingerprint_one(
    *,
    session: ClientSession,
    semaphore: asyncio.Semaphore,
    product_id: int,
    cover_image_url: str,
) -> FingerprintResult | None:
    async with semaphore:
        try:
            async with session.get(cover_image_url) as response:
                if response.status >= 400:
                    return None
                image_bytes = await response.read()
        except (ClientError, TimeoutError):
            return None

    try:
        fingerprint = image_fingerprint(image_bytes)
    except ImageFingerprintError:
        return None
    return FingerprintResult(
        product_id=product_id,
        cover_image_url=cover_image_url,
        ahash=fingerprint.ahash,
        dhash=fingerprint.dhash,
    )


def bulk_update_visual_fingerprints(results: list[FingerprintResult]) -> int:
    if not results:
        return 0
    now = timezone.now()
    products = [
        Product(
            id=result.product_id,
            cover_image_ahash=result.ahash,
            cover_image_dhash=result.dhash,
            cover_image_fingerprint_url=result.cover_image_url,
            cover_image_fingerprint_at=now,
        )
        for result in results
    ]
    Product.objects.bulk_update(
        products,
        fields=[
            "cover_image_ahash",
            "cover_image_dhash",
            "cover_image_fingerprint_url",
            "cover_image_fingerprint_at",
        ],
        batch_size=500,
    )
    return len(products)
