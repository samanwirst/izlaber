import hashlib
import json
from typing import Any

HASH_FIELDS = (
    "title",
    "description",
    "current_price",
    "old_price",
    "availability",
    "rating",
    "reviews_count",
    "seller",
    "specs",
    "image_urls",
)


def content_hash(payload: dict[str, Any]) -> str:
    stable = {field: payload.get(field) for field in HASH_FIELDS}
    encoded = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
