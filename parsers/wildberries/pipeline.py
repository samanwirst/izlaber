import logging
import math
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote_plus

from parsers.wildberries.client import (
    CatalogSegment,
    CategoryTask,
    WildberriesClient,
    WildberriesForbiddenError,
)
from parsers.wildberries.config import ParserConfig
from parsers.wildberries.normalizer import normalize_product
from parsers.wildberries.storage import CheckpointStore, ServerStorage

logger = logging.getLogger(__name__)


async def run_crawl(
    *,
    config: ParserConfig,
    mode: str,
    limit: int | None,
    resume: bool,
    dry_run: bool,
    category_limit: int | None = None,
) -> dict[str, Any]:
    checkpoint = CheckpointStore(config.state_dir)
    state = checkpoint.load() if resume else CheckpointStore.empty_state()
    if resume and state.get("mode") != mode:
        state = CheckpointStore.empty_state()
    if resume and mode != "resume" and state.get("completed"):
        state = CheckpointStore.empty_state()
    state["completed"] = False
    state["completed_status"] = None
    state["mode"] = mode

    storage = ServerStorage(config, dry_run=dry_run)
    previous_crawl_run_id = state.get("crawl_run_id") if resume else None
    crawl_run_id = previous_crawl_run_id or await storage.start_crawl_run(
        mode,
        {
            "dry_run": dry_run,
            "resume": resume,
            "previous_crawl_run_id": previous_crawl_run_id,
            "dest": config.destination_ids,
            "currency": config.currency_param,
            "price_split_enabled": config.price_split_enabled,
        },
    )
    state["crawl_run_id"] = crawl_run_id
    checkpoint.save(state)

    stats: dict[str, Any] = {
        "categories": 0,
        "segments": 0,
        "capped_segments": 0,
        "pages": 0,
        "discovered": 0,
        "processed": 0,
        "duplicates_skipped": 0,
        "seen": 0,
        "changed": 0,
        "created": 0,
        "updated": 0,
        "server_unchanged": 0,
        "skipped_unchanged": 0,
        "reactivated": 0,
        "failed": 0,
        "empty": 0,
        "unsupported": 0,
    }
    batch: list[dict[str, Any]] = []
    seen_runtime_ids: set[str] = set()
    processed_category_ids = set(state["processed_category_ids"])
    processed_segment_keys = set(state["processed_segment_keys"])
    failed_segment_keys = set(state["failed_segment_keys"])

    async def flush_batch() -> None:
        if not batch:
            return
        products = list(batch)
        batch.clear()
        source_product_ids = [
            str(product["source_product_id"])
            for product in products
            if product.get("source_product_id")
        ]
        for chunk in _chunks(source_product_ids, config.delta_compare_batch_size):
            await storage.record_seen_product_ids(crawl_run_id, chunk)
            stats["seen"] += len(chunk)

        existing_states: dict[str, dict[str, Any]] = {}
        for chunk in _chunks(source_product_ids, config.delta_compare_batch_size):
            existing_states.update(await storage.get_product_states(chunk))

        changed_products = []
        for product in products:
            existing_state = existing_states.get(str(product["source_product_id"]))
            if _needs_upsert(product, existing_state):
                changed_products.append(product)
            else:
                stats["skipped_unchanged"] += 1

        stats["changed"] += len(changed_products)
        for chunk in _chunks(changed_products, config.batch_size):
            result = await storage.upsert_products(chunk, crawl_run_id)
            stats["created"] += result.get("created_count", 0)
            stats["updated"] += result.get("updated_count", 0)
            stats["server_unchanged"] += result.get("unchanged_count", 0)
            stats["reactivated"] += result.get("reactivated_count", 0)
        checkpoint.save(state)

    try:
        async with WildberriesClient(config) as client:
            categories = await client.fetch_categories()
            if category_limit is not None:
                categories = categories[:category_limit]
            logger.info("Wildberries categories discovered: %s", len(categories))

            for category in categories:
                if category.source_category_id in processed_category_ids:
                    continue
                stats["categories"] += 1
                try:
                    segments = await client.build_segments(
                        category,
                        allow_price_split=limit is None,
                    )
                except WildberriesForbiddenError as error:
                    stats["unsupported"] += 1
                    logger.info("Skipping unsupported WB category %s: %s", category.path, error)
                    await storage.create_event(
                        crawl_run_id,
                        "info",
                        "wb_category_unsupported",
                        str(error),
                        url=category.url,
                    )
                    processed_category_ids.add(category.source_category_id)
                    state["processed_category_ids"].append(category.source_category_id)
                    checkpoint.save(state)
                    continue
                except Exception as error:
                    stats["failed"] += 1
                    logger.exception("Failed to build WB segments for %s", category.path)
                    await storage.create_event(
                        crawl_run_id,
                        "error",
                        "wb_segments_failed",
                        str(error),
                        url=category.url,
                    )
                    continue

                for segment in segments:
                    if segment.key in processed_segment_keys:
                        continue
                    stats["segments"] += 1
                    if segment.capped:
                        stats["capped_segments"] += 1
                    try:
                        await _process_segment(
                            client=client,
                            segment=segment,
                            config=config,
                            stats=stats,
                            batch=batch,
                            flush_batch=flush_batch,
                            seen_runtime_ids=seen_runtime_ids,
                            limit=limit,
                            state=state,
                            checkpoint=checkpoint,
                        )
                    except WildberriesForbiddenError as error:
                        stats["unsupported"] += 1
                        logger.info("Skipping unsupported WB segment %s: %s", segment.key, error)
                        processed_segment_keys.add(segment.key)
                        state["processed_segment_keys"].append(segment.key)
                        await storage.create_event(
                            crawl_run_id,
                            "info",
                            "wb_segment_unsupported",
                            str(error),
                            url=segment.category.url,
                            metadata={
                                "segment_key": segment.key,
                                "price_min_u": segment.price_min_u,
                                "price_max_u": segment.price_max_u,
                            },
                        )
                        checkpoint.save(state)
                        continue
                    except Exception as error:
                        stats["failed"] += 1
                        failed_segment_keys.add(segment.key)
                        if segment.key not in state["failed_segment_keys"]:
                            state["failed_segment_keys"].append(segment.key)
                        logger.exception("Failed to process WB segment %s", segment.key)
                        await storage.create_event(
                            crawl_run_id,
                            "error",
                            "wb_segment_failed",
                            str(error),
                            url=segment.category.url,
                            metadata={
                                "segment_key": segment.key,
                                "price_min_u": segment.price_min_u,
                                "price_max_u": segment.price_max_u,
                            },
                        )
                        checkpoint.save(state)
                        continue

                    processed_segment_keys.add(segment.key)
                    state["processed_segment_keys"].append(segment.key)
                    state["segment_next_pages"].pop(segment.key, None)
                    if segment.key in failed_segment_keys:
                        failed_segment_keys.remove(segment.key)
                        state["failed_segment_keys"] = [
                            key for key in state["failed_segment_keys"] if key != segment.key
                        ]
                    checkpoint.save(state)
                    if limit is not None and stats["processed"] >= limit:
                        break

                category_done = all(segment.key in processed_segment_keys for segment in segments)
                if category_done:
                    processed_category_ids.add(category.source_category_id)
                    state["processed_category_ids"].append(category.source_category_id)
                    checkpoint.save(state)
                    logger.info(
                        "WB category completed: %s segments=%s processed=%s changed=%s",
                        category.path,
                        len(segments),
                        stats["processed"],
                        stats["changed"],
                    )
                if limit is not None and stats["processed"] >= limit:
                    break

        await flush_batch()
        completion_status = _completion_status(stats, limit=limit)
        await storage.finish_crawl_run(
            crawl_run_id,
            status=completion_status,
            deactivate_unseen=(
                mode == "full"
                and limit is None
                and completion_status == "success"
                and stats["capped_segments"] == 0
            ),
            metadata=stats,
        )
        state["completed"] = completion_status == "success"
        state["completed_status"] = completion_status
        state["completed_at"] = datetime.now(UTC).isoformat()
        checkpoint.save(state)
        return stats
    except Exception:
        await storage.finish_crawl_run(
            crawl_run_id,
            status="failed",
            deactivate_unseen=False,
            metadata=stats,
        )
        state["completed"] = False
        state["completed_status"] = "failed"
        checkpoint.save(state)
        raise


async def run_search_backfill(
    *,
    config: ParserConfig,
    queries: list[str],
    limit: int,
    dry_run: bool,
) -> dict[str, Any]:
    storage = ServerStorage(config, dry_run=dry_run)
    crawl_run_id = await storage.start_crawl_run(
        "incremental",
        {
            "kind": "search_backfill",
            "dry_run": dry_run,
            "queries": queries,
            "limit": limit,
            "dest": config.destination_ids,
            "currency": config.currency_param,
        },
    )
    stats: dict[str, Any] = {
        "queries": 0,
        "pages": 0,
        "discovered": 0,
        "processed": 0,
        "duplicates_skipped": 0,
        "seen": 0,
        "changed": 0,
        "created": 0,
        "updated": 0,
        "server_unchanged": 0,
        "skipped_unchanged": 0,
        "reactivated": 0,
        "failed": 0,
        "empty": 0,
    }
    batch: list[dict[str, Any]] = []
    seen_runtime_ids: set[str] = set()

    async def flush_batch() -> None:
        if not batch:
            return
        await _flush_products(
            storage=storage,
            config=config,
            crawl_run_id=crawl_run_id,
            batch=batch,
            stats=stats,
        )

    try:
        async with WildberriesClient(config) as client:
            for query in queries:
                normalized_query = query.strip()
                if not normalized_query:
                    continue
                stats["queries"] += 1
                category = _search_category(normalized_query)
                segment = CatalogSegment(category=category, total=limit)
                page_count = max(1, math.ceil(limit / config.page_size))
                query_processed = 0
                for page in range(1, page_count + 1):
                    data = await client.fetch_search_page(normalized_query, page=page)
                    stats["pages"] += 1
                    products = data.get("products") or []
                    if not products:
                        stats["empty"] += 1
                        break
                    for raw in products:
                        if not isinstance(raw, dict):
                            continue
                        stats["discovered"] += 1
                        product_id = str(raw.get("id") or "")
                        if not product_id:
                            continue
                        if product_id in seen_runtime_ids:
                            stats["duplicates_skipped"] += 1
                            continue
                        normalized = normalize_product(
                            raw,
                            category=category,
                            segment=segment,
                            config=config,
                        )
                        if normalized is None:
                            continue
                        normalized["raw_data"]["search_backfill"] = {
                            "query": normalized_query,
                            "page": page,
                            "metadata": data.get("metadata"),
                        }
                        seen_runtime_ids.add(product_id)
                        batch.append(normalized)
                        stats["processed"] += 1
                        query_processed += 1
                        if len(batch) >= config.delta_compare_batch_size:
                            await flush_batch()
                        if query_processed >= limit:
                            break
                    await flush_batch()
                    if query_processed >= limit:
                        break
                logger.info(
                    "WB search backfill completed query=%r processed=%s changed=%s",
                    normalized_query,
                    stats["processed"],
                    stats["changed"],
                )

        await flush_batch()
        await storage.finish_crawl_run(
            crawl_run_id,
            status="success" if not stats["failed"] else "partial",
            deactivate_unseen=False,
            metadata=stats,
        )
        return stats
    except Exception:
        stats["failed"] += 1
        await storage.finish_crawl_run(
            crawl_run_id,
            status="failed",
            deactivate_unseen=False,
            metadata=stats,
        )
        raise


async def _process_segment(
    *,
    client: WildberriesClient,
    segment: CatalogSegment,
    config: ParserConfig,
    stats: dict[str, Any],
    batch: list[dict[str, Any]],
    flush_batch: Callable[[], Awaitable[None]],
    seen_runtime_ids: set[str],
    limit: int | None,
    state: dict[str, Any],
    checkpoint: CheckpointStore,
) -> None:
    if segment.total <= 0:
        stats["empty"] += 1
        return
    page_count = min(
        math.ceil(segment.total / config.page_size),
        config.max_pages_per_segment,
    )
    next_pages = state.setdefault("segment_next_pages", {})
    start_page = int(next_pages.get(segment.key) or 1)
    if start_page > page_count:
        return
    for page in range(start_page, page_count + 1):
        data = await client.fetch_catalog_page(
            segment.category,
            page=page,
            price_min_u=segment.price_min_u,
            price_max_u=segment.price_max_u,
        )
        stats["pages"] += 1
        products = data.get("products") or []
        if not products:
            stats["empty"] += 1
            break
        page_completed = True
        for raw in products:
            if not isinstance(raw, dict):
                continue
            stats["discovered"] += 1
            product_id = str(raw.get("id") or "")
            if not product_id:
                continue
            if product_id in seen_runtime_ids:
                stats["duplicates_skipped"] += 1
                continue
            normalized = normalize_product(
                raw,
                category=segment.category,
                segment=segment,
                config=config,
            )
            if normalized is None:
                continue
            seen_runtime_ids.add(product_id)
            batch.append(normalized)
            stats["processed"] += 1
            if len(batch) >= config.delta_compare_batch_size:
                await flush_batch()
            if limit is not None and stats["processed"] >= limit:
                page_completed = False
                break
        await flush_batch()
        if page_completed:
            next_pages[segment.key] = page + 1
            checkpoint.save(state)
        if stats["processed"] and stats["processed"] % 5_000 == 0:
            logger.info(
                "WB crawl progress: categories=%s segments=%s pages=%s processed=%s "
                "changed=%s duplicates=%s failed=%s",
                stats["categories"],
                stats["segments"],
                stats["pages"],
                stats["processed"],
                stats["changed"],
                stats["duplicates_skipped"],
                stats["failed"],
            )
        if page == page_count or page % 10 == 0:
            logger.info(
                "WB segment progress: %s page=%s/%s processed=%s changed=%s",
                segment.category.path,
                page,
                page_count,
                stats["processed"],
                stats["changed"],
            )
        if limit is not None and stats["processed"] >= limit:
            break


async def _flush_products(
    *,
    storage: ServerStorage,
    config: ParserConfig,
    crawl_run_id: int | None,
    batch: list[dict[str, Any]],
    stats: dict[str, Any],
) -> None:
    products = list(batch)
    batch.clear()
    source_product_ids = [
        str(product["source_product_id"])
        for product in products
        if product.get("source_product_id")
    ]
    for chunk in _chunks(source_product_ids, config.delta_compare_batch_size):
        await storage.record_seen_product_ids(crawl_run_id, chunk)
        stats["seen"] += len(chunk)

    existing_states: dict[str, dict[str, Any]] = {}
    for chunk in _chunks(source_product_ids, config.delta_compare_batch_size):
        existing_states.update(await storage.get_product_states(chunk))

    changed_products = []
    for product in products:
        existing_state = existing_states.get(str(product["source_product_id"]))
        if _needs_upsert(product, existing_state):
            changed_products.append(product)
        else:
            stats["skipped_unchanged"] += 1

    stats["changed"] += len(changed_products)
    for chunk in _chunks(changed_products, config.batch_size):
        result = await storage.upsert_products(chunk, crawl_run_id)
        stats["created"] += result.get("created_count", 0)
        stats["updated"] += result.get("updated_count", 0)
        stats["server_unchanged"] += result.get("unchanged_count", 0)
        stats["reactivated"] += result.get("reactivated_count", 0)


def _search_category(query: str) -> CategoryTask:
    return CategoryTask(
        source_category_id=f"search:{query.lower()}",
        name=query,
        path=f"Wildberries search > {query}",
        url=f"https://www.wildberries.uz/catalog/0/search.aspx?search={quote_plus(query)}",
        shard="search",
        query=f"query={query}",
        params={"query": query},
    )


def _completion_status(stats: dict[str, Any], *, limit: int | None) -> str:
    if stats["failed"]:
        return "partial"
    if limit is None and stats["capped_segments"]:
        return "partial"
    return "success"


def _needs_upsert(product: dict[str, Any], existing_state: dict[str, Any] | None) -> bool:
    if existing_state is None:
        return True
    return (
        existing_state.get("content_hash") != product.get("content_hash")
        or not existing_state.get("is_active", True)
    )


def _chunks(items: list, size: int):
    for index in range(0, len(items), size):
        yield items[index : index + size]
