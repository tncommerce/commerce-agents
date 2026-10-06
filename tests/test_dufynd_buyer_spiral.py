import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "examples/retail/data/dufynd_buyer_spiral_20261006.json"
LEGACY_PACKET = ROOT / "examples/retail/data/dufynd_first_money_publish_packets_20261004.json"
RENDERER = ROOT / "scripts/render_dufynd_buyer_spiral_20261006.py"
WORKFLOW = ROOT / ".github/workflows/dufynd-first-money-publish-render.yml"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_buyer_spiral_is_new_owner_gated_product_free_revision():
    spec = load(SPEC)
    legacy = load(LEGACY_PACKET)

    assert spec["content_id"] == "fragrance_buyer_spiral_20261006_01"
    assert spec["constraints"]["publishing_authorized"] is False
    assert spec["constraints"]["paid_tools"] is False
    assert spec["constraints"]["new_credits"] is False
    assert spec["constraints"]["product_assets"] is False
    assert spec["constraints"]["external_images"] is False
    assert spec["constraints"]["visual_quality_floor"] == 9.5
    assert spec["content_id"] not in {piece["content_id"] for piece in legacy["pieces"]}


def test_buyer_spiral_tiktok_copy_has_no_fake_click_path_or_claims():
    spec = load(SPEC)
    rendered_text = json.dumps(
        {
            "slides": spec["slides"],
            "caption": spec["caption"]["tiktok"],
            "qa": spec["qa"],
        },
        ensure_ascii=False,
    ).lower()

    assert "http://" not in rendered_text
    assert "https://" not in rendered_text
    assert "link im profil" not in rendered_text
    for forbidden in ("bessere stimmung", "mehr energie", "weniger stress", "fokus"):
        assert forbidden not in rendered_text


def test_buyer_spiral_renderer_preserves_platform_dimensions_and_owner_gate():
    source = RENDERER.read_text(encoding="utf-8")
    assert "IG = (1080, 1350)" in source
    assert "TT = (1080, 1920)" in source
    assert '"publish_action_taken": False' in source
    assert '"native_preview_pending": True' in source
    assert "publishing_authorized" in source


def test_no_spend_render_workflow_builds_buyer_spiral_after_merge():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "scripts/render_dufynd_buyer_spiral_20261006.py" in workflow
    assert "examples/retail/data/dufynd_buyer_spiral_20261006.json" in workflow
    assert "public/social/organic/fragrance_buyer_spiral_20261006_01" in workflow
