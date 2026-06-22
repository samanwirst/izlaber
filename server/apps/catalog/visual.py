from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from django.db import connection

from apps.catalog.models import Product

HASH_HEX_LENGTH = 16


class ImageFingerprintError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ImageFingerprint:
    ahash: str
    dhash: str


def image_fingerprint(image_bytes: bytes) -> ImageFingerprint:
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as error:
        raise ImageFingerprintError("Pillow is required for image fingerprinting") from error

    try:
        with Image.open(BytesIO(image_bytes)) as image:
            grayscale = image.convert("L")
            return ImageFingerprint(
                ahash=_average_hash(grayscale),
                dhash=_difference_hash(grayscale),
            )
    except (OSError, UnidentifiedImageError) as error:
        raise ImageFingerprintError("Cannot decode image") from error


def visual_search_product_ids(
    *,
    ahash: str,
    dhash: str,
    marketplace_code: str | None,
    active_only: bool,
    limit: int,
    max_distance: int,
) -> list[int]:
    if limit <= 0:
        return []
    ahash = _clean_hash(ahash)
    dhash = _clean_hash(dhash)
    if not ahash or not dhash:
        return []

    if connection.vendor == "postgresql":
        return _visual_search_product_ids_postgres(
            ahash=ahash,
            dhash=dhash,
            marketplace_code=marketplace_code,
            active_only=active_only,
            limit=min(limit, 100),
            max_distance=max(0, max_distance),
        )
    return _visual_search_product_ids_python(
        ahash=ahash,
        dhash=dhash,
        marketplace_code=marketplace_code,
        active_only=active_only,
        limit=min(limit, 100),
        max_distance=max(0, max_distance),
    )


def hamming_distance_hex(left: str, right: str) -> int:
    left_hash = _clean_hash(left)
    right_hash = _clean_hash(right)
    if not left_hash or not right_hash:
        return HASH_HEX_LENGTH * 4
    return (int(left_hash, 16) ^ int(right_hash, 16)).bit_count()


def _visual_search_product_ids_postgres(
    *,
    ahash: str,
    dhash: str,
    marketplace_code: str | None,
    active_only: bool,
    limit: int,
    max_distance: int,
) -> list[int]:
    filters = [
        "p.cover_image_ahash IS NOT NULL",
        "p.cover_image_dhash IS NOT NULL",
    ]
    params: list[object] = [ahash, dhash]
    if marketplace_code:
        filters.append("m.code = %s")
        params.append(marketplace_code)
    if active_only:
        filters.append("p.is_active = TRUE")
    params.append(max_distance)
    params.append(limit)

    where_sql = " AND ".join(filters)
    sql = f"""
        SELECT id
        FROM (
            SELECT
                p.id,
                (
                    bit_count((('x' || p.cover_image_ahash)::bit(64) # ('x' || %s)::bit(64))) +
                    bit_count((('x' || p.cover_image_dhash)::bit(64) # ('x' || %s)::bit(64)))
                ) AS visual_distance,
                p.rating,
                p.reviews_count,
                p.last_seen_at
            FROM catalog_product p
            JOIN catalog_marketplace m ON m.id = p.marketplace_id
            WHERE {where_sql}
        ) ranked
        WHERE visual_distance <= %s
        ORDER BY
            visual_distance ASC,
            rating DESC NULLS LAST,
            reviews_count DESC NULLS LAST,
            last_seen_at DESC
        LIMIT %s
    """
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        return [row[0] for row in cursor.fetchall()]


def _visual_search_product_ids_python(
    *,
    ahash: str,
    dhash: str,
    marketplace_code: str | None,
    active_only: bool,
    limit: int,
    max_distance: int,
) -> list[int]:
    queryset = Product.objects.filter(
        cover_image_ahash__isnull=False,
        cover_image_dhash__isnull=False,
    )
    if marketplace_code:
        queryset = queryset.filter(marketplace__code=marketplace_code)
    if active_only:
        queryset = queryset.filter(is_active=True)

    ranked: list[tuple[int, int, float, int, object]] = []
    for row in queryset.values_list(
        "id",
        "cover_image_ahash",
        "cover_image_dhash",
        "rating",
        "reviews_count",
        "last_seen_at",
    ).iterator(chunk_size=5000):
        product_id, product_ahash, product_dhash, rating, reviews_count, last_seen_at = row
        distance = hamming_distance_hex(ahash, product_ahash) + hamming_distance_hex(
            dhash,
            product_dhash,
        )
        if distance <= max_distance:
            ranked.append(
                (
                    distance,
                    -float(rating or 0),
                    -(reviews_count or 0),
                    -(last_seen_at.timestamp() if last_seen_at else 0),
                    product_id,
                )
            )

    ranked.sort()
    return [product_id for *_score, product_id in ranked[:limit]]


def _average_hash(image) -> str:
    resized = image.resize((8, 8))
    pixels = list(resized.getdata())
    average = sum(pixels) / len(pixels)
    value = 0
    for pixel in pixels:
        value = (value << 1) | int(pixel >= average)
    return f"{value:016x}"


def _difference_hash(image) -> str:
    resized = image.resize((9, 8))
    pixels = list(resized.getdata())
    value = 0
    for row in range(8):
        row_offset = row * 9
        for column in range(8):
            left = pixels[row_offset + column]
            right = pixels[row_offset + column + 1]
            value = (value << 1) | int(left > right)
    return f"{value:016x}"


def _clean_hash(value: str | None) -> str:
    if not isinstance(value, str):
        return ""
    value = value.strip().lower()
    if len(value) != HASH_HEX_LENGTH:
        return ""
    if any(character not in "0123456789abcdef" for character in value):
        return ""
    return value
