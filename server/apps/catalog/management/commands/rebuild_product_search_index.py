from itertools import islice

from django.core.management.base import BaseCommand

from apps.catalog.models import Product, ProductSearchTerm
from apps.catalog.search import product_search_terms


class Command(BaseCommand):
    help = "Rebuild product token search index used by bot/API search."

    def add_arguments(self, parser):
        parser.add_argument("--marketplace", default="uzum")
        parser.add_argument("--chunk-size", type=int, default=5000)
        parser.add_argument("--insert-batch-size", type=int, default=50000)

    def handle(self, *args, **options):
        marketplace = options["marketplace"]
        chunk_size = options["chunk_size"]
        insert_batch_size = options["insert_batch_size"]

        deleted_count, _ = ProductSearchTerm.objects.filter(
            product__marketplace__code=marketplace
        ).delete()
        self.stdout.write(f"Deleted {deleted_count} old search terms.")

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
                terms = product_search_terms(
                    title=title,
                    brand=brand,
                    category_path_text=category_path_text,
                    source_product_id=source_product_id,
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

                if len(pending) >= insert_batch_size:
                    ProductSearchTerm.objects.bulk_create(
                        pending,
                        batch_size=insert_batch_size,
                        ignore_conflicts=True,
                    )
                    created_terms += len(pending)
                    pending.clear()

            if indexed_products % 50000 == 0:
                self.stdout.write(f"Indexed {indexed_products}/{total_products} products...")

        if pending:
            ProductSearchTerm.objects.bulk_create(
                pending,
                batch_size=insert_batch_size,
                ignore_conflicts=True,
            )
            created_terms += len(pending)

        self.stdout.write(
            self.style.SUCCESS(
                f"Indexed {indexed_products} products with {created_terms} search terms."
            )
        )
