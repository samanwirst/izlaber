from itertools import islice

from django.core.management.base import BaseCommand
from django.db import connection

from apps.catalog.models import Product, ProductSearchTerm
from apps.catalog.search import product_search_terms, product_search_text


class Command(BaseCommand):
    help = "Rebuild product token search index used by bot/API search."

    def add_arguments(self, parser):
        parser.add_argument("--marketplace", default="uzum")
        parser.add_argument("--chunk-size", type=int, default=5000)
        parser.add_argument("--insert-batch-size", type=int, default=50000)
        parser.add_argument(
            "--skip-token-index",
            action="store_true",
            help="Only refresh Product.search_text; useful for PostgreSQL FTS.",
        )

    def handle(self, *args, **options):
        marketplace = options["marketplace"]
        chunk_size = options["chunk_size"]
        insert_batch_size = options["insert_batch_size"]
        skip_token_index = options["skip_token_index"]

        if skip_token_index:
            self.stdout.write("Skipping token index rebuild; refreshing search_text only.")
        else:
            deleted_count, _ = ProductSearchTerm.objects.filter(
                product__marketplace__code=marketplace
            ).delete()
            self.stdout.write(f"Deleted {deleted_count} old search terms.")

        if connection.vendor == "postgresql" and not skip_token_index:
            self.stdout.write(
                self.style.WARNING(
                    "PostgreSQL search uses Product.search_text FTS. "
                    "Consider --skip-token-index to avoid rebuilding millions of token rows."
                )
            )

        products = Product.objects.filter(marketplace__code=marketplace).values_list(
            "id",
            "marketplace__code",
            "title",
            "brand",
            "category_path_text",
            "source_product_id",
            "is_active",
            "rating",
            "reviews_count",
            "last_seen_at",
        )
        total_products = products.count()
        indexed_products = 0
        created_terms = 0
        pending: list[ProductSearchTerm] = []
        pending_products: list[Product] = []

        iterator = products.iterator(chunk_size=chunk_size)
        while rows := list(islice(iterator, chunk_size)):
            for (
                product_id,
                marketplace_code,
                title,
                brand,
                category_path_text,
                source_product_id,
                is_active,
                rating,
                reviews_count,
                last_seen_at,
            ) in rows:
                terms = (
                    {}
                    if skip_token_index
                    else product_search_terms(
                        title=title,
                        brand=brand,
                        category_path_text=category_path_text,
                        source_product_id=source_product_id,
                    )
                )
                pending_products.append(
                    Product(
                        id=product_id,
                        search_text=product_search_text(
                            title=title,
                            brand=brand,
                            category_path_text=category_path_text,
                            source_product_id=source_product_id,
                        ),
                    )
                )
                pending.extend(
                    ProductSearchTerm(
                        product_id=product_id,
                        marketplace_code=marketplace_code,
                        term=term,
                        weight=weight,
                        product_is_active=is_active,
                        product_rating=rating,
                        product_reviews_count=reviews_count,
                        product_last_seen_at=last_seen_at,
                    )
                    for term, weight in terms.items()
                )
                indexed_products += 1

                if len(pending) >= insert_batch_size or len(pending_products) >= chunk_size:
                    created_terms += _flush_updates(
                        pending_products=pending_products,
                        pending_terms=pending,
                        chunk_size=chunk_size,
                        insert_batch_size=insert_batch_size,
                    )

            if indexed_products % 50000 == 0:
                self.stdout.write(f"Indexed {indexed_products}/{total_products} products...")

        if pending_products or pending:
            created_terms += _flush_updates(
                pending_products=pending_products,
                pending_terms=pending,
                chunk_size=chunk_size,
                insert_batch_size=insert_batch_size,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Indexed {indexed_products} products with {created_terms} search terms."
            )
        )


def _flush_updates(
    *,
    pending_products: list[Product],
    pending_terms: list[ProductSearchTerm],
    chunk_size: int,
    insert_batch_size: int,
) -> int:
    if pending_products:
        Product.objects.bulk_update(
            pending_products,
            ["search_text"],
            batch_size=chunk_size,
        )
    if pending_terms:
        ProductSearchTerm.objects.bulk_create(
            pending_terms,
            batch_size=insert_batch_size,
            ignore_conflicts=True,
        )
    created_terms = len(pending_terms)
    pending_products.clear()
    pending_terms.clear()
    return created_terms
