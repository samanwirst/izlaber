from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0007_product_cover_image_fingerprint"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserPreference",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("telegram_user_id", models.BigIntegerField(db_index=True, unique=True)),
                ("language_code", models.SlugField(default="uz", max_length=8)),
            ],
            options={
                "ordering": ("telegram_user_id",),
            },
        ),
    ]
