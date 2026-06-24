import json

from apps.crawling.management.commands.audit_uzum_category_coverage import _write_parser_shards


def test_write_parser_shards_skips_processed_urls(tmp_path):
    checkpoint = tmp_path / "checkpoint.json"
    checkpoint.write_text(
        json.dumps(
            {
                "processed_category_urls": [
                    "https://uzum.uz/ru/category/processed-2",
                ]
            }
        )
    )
    output_dir = tmp_path / "shards"

    report = _write_parser_shards(
        [
            {
                "url": "https://uzum.uz/ru/category/high-gap-1",
                "gap": 100,
            },
            {
                "url": "https://uzum.uz/ru/category/processed-2",
                "gap": 90,
            },
            {
                "url": "https://uzum.uz/ru/category/medium-gap-3",
                "gap": 50,
            },
            {
                "url": "",
                "gap": 40,
            },
            {
                "url": "https://uzum.uz/ru/category/no-gap-4",
                "gap": 0,
            },
        ],
        output_dir=output_dir,
        shard_count=2,
        state_prefix=".parser_state/uzum_market/shards/shard",
        exclude_paths=[checkpoint],
    )

    shard_text = "\n".join(path.read_text() for path in sorted(output_dir.glob("*.env")))

    assert report == {
        "shards": 2,
        "categories": 2,
        "gap_total": 150,
        "excluded_processed_categories": 1,
    }
    assert "UZUM_STATE_DIR=.parser_state/uzum_market/shards/shard01-state" in shard_text
    assert "UZUM_STATE_DIR=.parser_state/uzum_market/shards/shard02-state" in shard_text
    assert "https://uzum.uz/ru/category/high-gap-1" in shard_text
    assert "https://uzum.uz/ru/category/medium-gap-3" in shard_text
    assert "https://uzum.uz/ru/category/processed-2" not in shard_text
    assert "https://uzum.uz/ru/category/no-gap-4" not in shard_text
