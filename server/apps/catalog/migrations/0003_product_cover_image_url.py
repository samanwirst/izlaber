from django.db import migrations, models


def backfill_cover_image_url(apps, schema_editor):
    Product = apps.get_model("catalog", "Product")
    batch = []
    for product in Product.objects.only("id", "cover_image_url", "image_urls").iterator(
        chunk_size=2_000
    ):
        if product.cover_image_url:
            continue
        image_urls = product.image_urls or []
        if not image_urls:
            continue
        product.cover_image_url = image_urls[0]
        batch.append(product)
        if len(batch) >= 2_000:
            Product.objects.bulk_update(batch, ["cover_image_url"])
            batch.clear()
    if batch:
        Product.objects.bulk_update(batch, ["cover_image_url"])


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0002_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="cover_image_url",
            field=models.URLField(blank=True, max_length=1024, null=True),
        ),
        migrations.RunPython(backfill_cover_image_url, migrations.RunPython.noop),
    ]
