from pathlib import Path

SQL = Path(
    "supabase/migrations/20261007080500_jarvis_content_performance_learning_v1.sql"
).read_text()


def test_learning_uses_latest_snapshot_per_social_post():
    assert "distinct on (platform, platform_content_id)" in SQL
    assert "order by platform, platform_content_id, measured_at desc" in SQL


def test_learning_is_directional_not_auto_mutating():
    assert "'confidence'" in SQL
    assert "directional_small_sample" in SQL
    assert "'automatic_priority_mutation',false" in SQL
    assert "not a universal platform rule" in SQL


def test_learning_compares_tiktok_photo_and_video():
    for token in (
        "photo_median_views",
        "video_median_views",
        "photo_to_video_median_ratio",
        "prioritize_photo_carousel_for_reach",
        "best_video",
    ):
        assert token in SQL


def test_learning_worker_consumes_only_performance_events():
    assert "event_type='content_performance_added'" in SQL
    assert "source_type='content_performance'" in SQL
    assert "processing_status='content_performance_learning_v1'" in SQL


def test_learning_cycle_is_zero_spend_and_non_publishing():
    for forbidden in (
        "gmail.send",
        "social.publish",
        "budget.spend",
        "main.merge",
        "commerce.activate",
        "shell.execute",
    ):
        assert forbidden in SQL
    assert "'new_spend_usd',0" in SQL
    assert "dufynd-content-performance-learning-v1" in SQL
    assert "*/10 * * * *" in SQL
