from pathlib import Path

SQL = Path(\n    "supabase/migrations/20261007075500_jarvis_performance_learning_schema_fix_v1.sql"\n).read_text()


def test_trigger_does_not_reference_nonexistent_performance_column():
    assert "new.content_idea_id" not in SQL
    assert "dufynd_content_assets" in SQL
    assert "a.content_idea_id" in SQL


def test_trigger_supports_metadata_fallback_for_unlinked_social_posts():
    assert "new.metadata->>'content_idea_id'" in SQL
    assert "coalesce(" in SQL


def test_learning_event_contains_enough_performance_context():
    for field in (
        "'content_asset_id'",
        "'content_idea_id'",
        "'platform_content_id'",
        "'views'",
        "'impressions'",
        "'avg_watch_time_seconds'",
        "'shares'",
        "'saves'",
        "'site_clicks'",
        "'affiliate_clicks'",
        "'conversions'",
        "'revenue_eur'",
        "'metadata'",
    ):
        assert field in SQL


def test_migration_asserts_asset_schema_contract():
    assert "dufynd_content_assets" in SQL
    assert "raise exception 'content asset linkage missing" in SQL
