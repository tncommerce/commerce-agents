from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from scripts.dufynd_worker_evidence import (
    ATTRIBUTION,
    CONTENT,
    MAX_PROMPT_BYTES,
    encode,
    pack_evidence,
    projection_rows,
    source_text,
)


def task(
    domain="research", instruction="Audit landing attribution src cmp content sid clickout session"
):
    return {"task_id": "audit", "domain": domain, "instruction": instruction, "title": instruction}


def test_live_repository_pack_is_deterministic_and_bounded():
    for item in (
        task(),
        task(
            "content",
            "Prioritize existing pilot preview scripts voiceover social copy under Naxos quality floor",
        ),
    ):
        a = pack_evidence(item, head="a" * 40)
        assert a == pack_evidence(item, head="a" * 40)
        assert len(encode(a)) <= MAX_PROMPT_BYTES
        assert len(a["repository_evidence"]) >= 10
        paths = {s["path"] for s in a["repository_evidence"]}
        assert paths <= set(ATTRIBUTION if item["domain"] == "research" else CONTENT)
        for source in a["repository_evidence"]:
            raw = (Path(__file__).resolve().parents[1] / source["path"]).read_bytes()
            assert source["sha256"] == hashlib.sha256(raw).hexdigest()
            assert source.get("line_ranges") or source.get("data")
        assert all(s.get("complete") or s.get("omission_reason") for s in a["repository_evidence"])


def test_arbitrary_task_path_cannot_extend_allowlist(tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("PRIVATE")
    item = task(instruction="attribution inspect secret.txt ../../etc/passwd")
    packet = pack_evidence(item, head="a" * 40, root=tmp_path)
    assert packet["repository_evidence"] == []
    assert {s["path"] for s in packet["omitted_sources"]} == set(ATTRIBUTION)


def test_sensitive_and_symlink_sources_fail_closed(tmp_path):
    path = tmp_path / ATTRIBUTION[0]
    path.parent.mkdir(parents=True)
    path.write_text("sk-ant-" + "x" * 40)
    packet = pack_evidence(task(), head="a" * 40, root=tmp_path)
    assert packet["omitted_sources"][0]["reason"] == "secret_marker"
    path.unlink()
    path.symlink_to(tmp_path / "outside")
    assert (
        pack_evidence(task(), head="a" * 40, root=tmp_path)["omitted_sources"][0]["reason"]
        == "symlink_disallowed"
    )


def test_unknown_capability_and_oversized_metadata_rejected():
    with pytest.raises(ValueError, match="unsupported_evidence"):
        pack_evidence(task("research", "Read any file"), head=None)
    with pytest.raises(ValueError, match="metadata"):
        pack_evidence(task(instruction="attribution" + "x" * 10000), head=None)


def test_hash_is_over_exact_packet_before_digest():
    packet = pack_evidence(task(), head="a" * 40)
    digest = packet.pop("packet_sha256")
    assert digest == hashlib.sha256(encode(packet)).hexdigest()
    json.dumps(packet)


def test_all_three_content_batches_have_full_scripts_and_voiceover_specs():
    packet = pack_evidence(
        task("content", "pilot preview scripts voiceover subtitles social copy"), head="a" * 40
    )
    sources = {s["path"]: s for s in packet["repository_evidence"]}
    for batch in (1, 2, 3):
        name = f"examples/retail/data/scentai_pilot_batch_{batch:02d}.json"
        assert "voiceover" in source_text(sources[name])
        assert (
            f"examples/retail/data/scentai_pilot_batch_{batch:02d}_voiceover_spec.json" in sources
        )


def test_content_families_are_balanced_and_partial_media_is_explicit():
    packet = pack_evidence(
        task("content", "pilot preview scripts voiceover subtitles social copy"), head="a" * 40
    )
    sources = {s["path"]: s for s in packet["repository_evidence"]}
    for batch in (1, 2, 3):
        for suffix in ("subtitles", "social_copy"):
            source = sources[f"examples/retail/data/scentai_pilot_batch_{batch:02d}_{suffix}.json"]
            assert not source.get("complete")
            assert source["omission_reason"]
            assert len(projection_rows(source, "items" if suffix == "subtitles" else "posts")) == 5
    assert "examples/retail/data/dufynd_high_end_launch_assets.json" in sources
    assert "examples/retail/data/scentai_content_pipeline_status.json" in sources
    assert any("creative_learning" in path for path in sources)


def test_exact_live_content_task_keeps_learning_quality_floor_and_pipeline():
    live_task = {
        "task_id": "jarvis_content_preview_priority_20261001",
        "title": "Prioritize existing preview reserve without spend",
        "instruction": "Read-only audit of the 15 existing DUFYND pilot preview MP4s, scripts, subtitle drafts, social copy and current creative-learning documents. Select up to three strongest candidates for the next no-spend finalization wave under the current Naxos-level quality floor. Explicitly exclude rejected/rebuild-only Sillage/Haltbarkeit and EDP-vs-EDT. Distinguish what can be done with operator-recorded voiceover and local final rendering from anything that would require paid generation. Do not publish, spend credits, regenerate locked high-end assets, edit repository files or infer live social performance.",
        "domain": "content",
        "dependencies": [],
    }
    packet = pack_evidence(live_task, head="a" * 40)
    paths = {s["path"] for s in packet["repository_evidence"]}
    assert "docs/dufynd_creative_learning_library.md" in paths
    assert "examples/retail/data/dufynd_high_end_launch_assets.json" in paths
    assert "examples/retail/data/scentai_content_pipeline_status.json" in paths
    for batch in (1, 2, 3):
        for suffix in ("", "_voiceover_spec", "_subtitles", "_social_copy"):
            assert f"examples/retail/data/scentai_pilot_batch_{batch:02d}{suffix}.json" in paths
    assert len(encode(packet)) <= MAX_PROMPT_BYTES
