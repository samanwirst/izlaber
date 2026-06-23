import logging
from datetime import UTC, datetime
from urllib.parse import urlencode, urlparse

from parsers.uzum_market.browser import BrowserBlockedError, UzumBrowserClient
from parsers.uzum_market.config import ParserConfig
from parsers.uzum_market.discovery import UzumDiscovery
from parsers.uzum_market.storage import CheckpointStore, ServerStorage

logger = logging.getLogger(__name__)


async def run_crawl(
    *,
    config: ParserConfig,
    mode: str,
    limit: int | None,
    resume: bool,
    dry_run: bool,
) -> dict:
    checkpoint = CheckpointStore(config.state_dir)
    loaded_state = checkpoint.load() if resume else CheckpointStore.empty_state()
    previous_crawl_run_id = loaded_state.get("crawl_run_id") if resume else None
    if resume and mode != "resume" and loaded_state.get("completed"):
        state = CheckpointStore.empty_state()
    else:
        state = loaded_state
    state["completed"] = False
    state["completed_status"] = None
    storage = ServerStorage(config, dry_run=dry_run)
    crawl_run_id = await storage.start_crawl_run(
        mode,
        {"dry_run": dry_run, "resume": resume, "previous_crawl_run_id": previous_crawl_run_id},
    )
    state["crawl_run_id"] = crawl_run_id
    checkpoint.save(state)

    stats = {
        "categories": 0,
        "discovered": 0,
        "processed": 0,
        "seen": 0,
        "seeded_seen": 0,
        "changed": 0,
        "created": 0,
        "updated": 0,
        "server_unchanged": 0,
        "skipped_unchanged": 0,
        "skipped_existing_without_category": 0,
        "reactivated": 0,
        "failed": 0,
    }
    batch: list[dict] = []
    discovered_urls = set(state["discovered_urls"])
    processed_ids = set(state["processed_product_ids"])
    processed_category_urls = set(state["processed_category_urls"])
    processed_category_page_urls = set(state["processed_category_page_urls"])
    failed_urls = set(state["failed_urls"])
    blocked_urls = set(state["blocked_urls"])

    if processed_ids:
        stats["seeded_seen"] = await _record_seen_product_ids(
            storage,
            crawl_run_id,
            list(processed_ids),
            config.delta_compare_batch_size,
        )

    async with UzumBrowserClient(config) as client:
        discovery = UzumDiscovery(client, config)
        try:
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
                await storage.record_seen_product_ids(crawl_run_id, source_product_ids)
                stats["seen"] += len(source_product_ids)

                existing_states = await storage.get_product_states(source_product_ids)
                changed_products = []
                skipped_unchanged = 0
                for product in products:
                    existing_state = existing_states.get(str(product["source_product_id"]))
                    if not _needs_upsert(product, existing_state):
                        skipped_unchanged += 1
                        continue
                    if existing_state is not None and not _has_category(product):
                        stats["skipped_existing_without_category"] += 1
                        continue
                    changed_products.append(product)
                stats["skipped_unchanged"] += skipped_unchanged
                stats["changed"] += len(changed_products)
                for chunk in _chunks(changed_products, config.batch_size):
                    result = await storage.upsert_products(chunk, crawl_run_id)
                    stats["created"] += result.get("created_count", 0)
                    stats["updated"] += result.get("updated_count", 0)
                    stats["server_unchanged"] += result.get("unchanged_count", 0)
                    stats["reactivated"] += result.get("reactivated_count", 0)
                checkpoint.save(state)

            async for category_url in discovery.discover():
                if category_url in processed_category_urls:
                    continue
                stats["categories"] += 1
                try:
                    category_page_urls = await client.collect_category_page_urls(category_url)
                except BrowserBlockedError as error:
                    logger.warning("%s", error)
                    if category_url not in blocked_urls:
                        blocked_urls.add(category_url)
                        state["blocked_urls"].append(category_url)
                    await storage.create_event(
                        crawl_run_id,
                        "warning",
                        "blocked",
                        str(error),
                        url=category_url,
                    )
                    raise
                except Exception as error:
                    logger.exception("Failed to parse %s", category_url)
                    if category_url not in failed_urls:
                        failed_urls.add(category_url)
                        state["failed_urls"].append(category_url)
                    stats["failed"] += 1
                    await storage.create_event(
                        crawl_run_id,
                        "error",
                        "category_parse_failed",
                        str(error),
                        url=category_url,
                    )
                    continue
                if category_url in failed_urls:
                    failed_urls.remove(category_url)
                    state["failed_urls"] = [
                        failed_url
                        for failed_url in state["failed_urls"]
                        if failed_url != category_url
                    ]

                for category_page_url in category_page_urls:
                    if category_page_url in processed_category_page_urls:
                        continue
                    try:
                        products = await client.collect_listing_products(category_page_url)
                    except BrowserBlockedError as error:
                        logger.warning("%s", error)
                        if category_page_url not in blocked_urls:
                            blocked_urls.add(category_page_url)
                            state["blocked_urls"].append(category_page_url)
                        await storage.create_event(
                            crawl_run_id,
                            "warning",
                            "blocked",
                            str(error),
                            url=category_page_url,
                        )
                        raise
                    except Exception as error:
                        logger.exception("Failed to parse %s", category_page_url)
                        if category_page_url not in failed_urls:
                            failed_urls.add(category_page_url)
                            state["failed_urls"].append(category_page_url)
                        stats["failed"] += 1
                        await storage.create_event(
                            crawl_run_id,
                            "error",
                            "category_page_parse_failed",
                            str(error),
                            url=category_page_url,
                        )
                        continue
                    if category_page_url in failed_urls:
                        failed_urls.remove(category_page_url)
                        state["failed_urls"] = [
                            failed_url
                            for failed_url in state["failed_urls"]
                            if failed_url != category_page_url
                        ]

                    for product in products:
                        stats["discovered"] += 1
                        url = product["canonical_url"]
                        if url not in discovered_urls:
                            discovered_urls.add(url)
                            state["discovered_urls"].append(url)
                        product_id = product["source_product_id"]
                        if product_id and product_id in processed_ids:
                            continue
                        batch.append(product)
                        if product_id:
                            state["processed_product_ids"].append(product_id)
                            processed_ids.add(product_id)
                        stats["processed"] += 1
                        if len(batch) >= config.delta_compare_batch_size:
                            await flush_batch()
                        if stats["processed"] and stats["processed"] % 1_000 == 0:
                            logger.info(
                                "Uzum crawl progress: categories=%s pages=%s "
                                "processed=%s changed=%s skipped_unchanged=%s "
                                "discovered=%s failed=%s",
                                stats["categories"],
                                len(processed_category_page_urls),
                                stats["processed"],
                                stats["changed"],
                                stats["skipped_unchanged"],
                                stats["discovered"],
                                len(failed_urls),
                            )
                        if limit is not None and stats["processed"] >= limit:
                            break
                    processed_category_page_urls.add(category_page_url)
                    state["processed_category_page_urls"].append(category_page_url)
                    checkpoint.save(state)
                    if limit is not None and stats["processed"] >= limit:
                        break
                category_completed = all(
                    page_url in processed_category_page_urls for page_url in category_page_urls
                )
                if category_completed:
                    processed_category_urls.add(category_url)
                    state["processed_category_urls"].append(category_url)
                    failed_urls = _clear_failed_category_urls(
                        state,
                        failed_urls,
                        category_url,
                    )
                    checkpoint.save(state)
                    logger.info(
                        "Uzum category completed: %s pages=%s processed=%s failed=%s",
                        category_url,
                        len(category_page_urls),
                        stats["processed"],
                        len(failed_urls),
                    )
                if limit is not None and stats["processed"] >= limit:
                    break

            await flush_batch()
            completion_status = "success" if stats["failed"] == 0 else "partial"
            await storage.finish_crawl_run(
                crawl_run_id,
                status=completion_status,
                deactivate_unseen=(
                    mode == "full" and limit is None and completion_status == "success"
                ),
                metadata=stats,
            )
            state["completed"] = completion_status == "success"
            state["completed_status"] = completion_status
            state["completed_at"] = datetime.now(UTC).isoformat()
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

    checkpoint.save(state)
    return stats


async def run_search_backfill(
    *,
    config: ParserConfig,
    queries: list[str],
    limit: int | None,
    dry_run: bool,
) -> dict:
    normalized_queries = []
    seen_queries = set()
    for query in queries:
        normalized = " ".join(query.split())
        key = normalized.casefold()
        if not normalized or key in seen_queries:
            continue
        normalized_queries.append(normalized)
        seen_queries.add(key)

    storage = ServerStorage(config, dry_run=dry_run)
    crawl_run_id = await storage.start_crawl_run(
        "search_backfill",
        {"dry_run": dry_run, "queries": normalized_queries, "limit_per_query": limit},
    )
    stats = {
        "queries": len(normalized_queries),
        "discovered": 0,
        "seen": 0,
        "changed": 0,
        "created": 0,
        "updated": 0,
        "server_unchanged": 0,
        "skipped_unchanged": 0,
        "reactivated": 0,
        "failed": 0,
    }

    try:
        async with UzumBrowserClient(config) as client:
            for query in normalized_queries:
                try:
                    products = await client.collect_search_products(query, limit=limit)
                except BrowserBlockedError as error:
                    logger.warning("%s", error)
                    await storage.create_event(
                        crawl_run_id,
                        "warning",
                        "blocked",
                        str(error),
                        url=_search_url(query),
                    )
                    raise
                except Exception as error:
                    logger.exception("Failed to backfill Uzum search query %r", query)
                    stats["failed"] += 1
                    await storage.create_event(
                        crawl_run_id,
                        "error",
                        "search_backfill_failed",
                        str(error),
                        url=_search_url(query),
                    )
                    continue

                stats["discovered"] += len(products)
                source_product_ids = [
                    str(product["source_product_id"])
                    for product in products
                    if product.get("source_product_id")
                ]
                await storage.record_seen_product_ids(crawl_run_id, source_product_ids)
                stats["seen"] += len(source_product_ids)

                existing_states = await storage.get_product_states(source_product_ids)
                changed_products = [
                    product
                    for product in products
                    if _needs_upsert(
                        product,
                        existing_states.get(str(product["source_product_id"])),
                    )
                ]
                stats["skipped_unchanged"] += len(products) - len(changed_products)
                stats["changed"] += len(changed_products)
                for chunk in _chunks(changed_products, config.batch_size):
                    result = await storage.upsert_products(chunk, crawl_run_id)
                    stats["created"] += result.get("created_count", 0)
                    stats["updated"] += result.get("updated_count", 0)
                    stats["server_unchanged"] += result.get("unchanged_count", 0)
                    stats["reactivated"] += result.get("reactivated_count", 0)

        completion_status = "success" if stats["failed"] == 0 else "partial"
        await storage.finish_crawl_run(
            crawl_run_id,
            status=completion_status,
            deactivate_unseen=False,
            metadata=stats,
        )
        return stats
    except Exception:
        await storage.finish_crawl_run(
            crawl_run_id,
            status="failed",
            deactivate_unseen=False,
            metadata=stats,
        )
        raise


async def _record_seen_product_ids(
    storage: ServerStorage,
    crawl_run_id: int | None,
    source_product_ids: list[str],
    batch_size: int,
) -> int:
    seen_count = 0
    for chunk in _chunks(source_product_ids, batch_size):
        await storage.record_seen_product_ids(crawl_run_id, chunk)
        seen_count += len(chunk)
    return seen_count


def _chunks(items: list, size: int):
    for index in range(0, len(items), size):
        yield items[index : index + size]


def _search_url(query: str) -> str:
    return f"https://uzum.uz/ru/search?{urlencode({'query': query})}"


def _needs_upsert(product: dict, existing_state: dict | None) -> bool:
    if existing_state is None:
        return True
    if not existing_state.get("is_active", True):
        return True
    return existing_state.get("content_hash") != product["content_hash"]


def _has_category(product: dict) -> bool:
    category = product.get("category") or {}
    return bool(
        product.get("category_path_text")
        or category.get("name")
        or category.get("path_text")
    )


def _clear_failed_category_urls(
    state: dict,
    failed_urls: set[str],
    category_url: str,
) -> set[str]:
    category_path = urlparse(category_url).path
    state["failed_urls"] = [
        failed_url
        for failed_url in state["failed_urls"]
        if urlparse(failed_url).path != category_path
    ]
    return set(state["failed_urls"])
