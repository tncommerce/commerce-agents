from retail.api.merchant_feed_snapshot import (
    changed_snapshot_files,
    file_sha256,
)


def test_snapshot_guard_accepts_unchanged_files(
    tmp_path,
) -> None:
    feed = tmp_path / "feed.json"
    mappings = tmp_path / "mappings.json"

    feed.write_text('{"offers":[]}', encoding="utf-8")
    mappings.write_text('{"mappings":[]}', encoding="utf-8")

    changed = changed_snapshot_files(
        feed_path=feed,
        expected_feed_sha256=file_sha256(feed),
        mappings_path=mappings,
        expected_mappings_sha256=file_sha256(mappings),
    )

    assert changed == []


def test_snapshot_guard_detects_changed_files(
    tmp_path,
) -> None:
    feed = tmp_path / "feed.json"
    mappings = tmp_path / "mappings.json"

    feed.write_text('{"offers":[]}', encoding="utf-8")
    mappings.write_text('{"mappings":[]}', encoding="utf-8")

    feed_hash = file_sha256(feed)
    mappings_hash = file_sha256(mappings)

    feed.write_text(
        '{"offers":[{"offer_id":"changed"}]}',
        encoding="utf-8",
    )
    mappings.write_text(
        '{"mappings":[{"product_id":"changed"}]}',
        encoding="utf-8",
    )

    changed = changed_snapshot_files(
        feed_path=feed,
        expected_feed_sha256=feed_hash,
        mappings_path=mappings,
        expected_mappings_sha256=mappings_hash,
    )

    assert changed == [
        "feed",
        "mappings",
    ]
