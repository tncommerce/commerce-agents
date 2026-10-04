"""Deterministic public-repository evidence; no tools, provider calls or arbitrary paths."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_PROMPT_BYTES = 30000
MAX_SOURCE_BYTES = 262144
MAX_TEXT_BYTES = 500

ATTRIBUTION = (
    "examples/retail/storefront-web/lib/analytics.ts",
    "examples/retail/storefront-web/components/AcquisitionAnalytics.tsx",
    "examples/retail/storefront-web/components/AcquisitionInternalLink.tsx",
    "examples/retail/storefront-web/components/ComparisonAnalytics.tsx",
    "examples/retail/storefront-web/components/FragranceOffers.tsx",
    "examples/retail/storefront-web/lib/api.ts",
    "examples/retail/api/main.py",
    "examples/retail/api/analytics.py",
    "examples/retail/api/merchant_offers.py",
    "examples/retail/api/tests/test_clickout_analytics_correlation.py",
    "examples/retail/storefront-web/scripts/test-analytics-session-ownership.mjs",
    "examples/retail/storefront-web/scripts/home-navigation-attribution-qa.mjs",
    "examples/retail/storefront-web/scripts/guided-link-attribution-qa.mjs",
    "examples/retail/data/scentai_launch_attribution.md",
)
CONTENT = (
    (
        "docs/dufynd_creative_learning_library.md",
        "examples/retail/data/dufynd_high_end_launch_assets.json",
        "examples/retail/data/scentai_content_pipeline_status.json",
        "examples/retail/data/dufynd_content_strategy.json",
        "examples/retail/data/dufynd_content_buffer_plan.json",
        "docs/dufynd_creative_learning_batch_48_63.md",
        "docs/dufynd_creative_learning_batch_64_69.md",
        "examples/retail/data/dufynd_high_end_pre_publish_checklist.json",
    )
    + tuple(
        f"examples/retail/data/scentai_pilot_batch_{batch:02d}{suffix}.json"
        for batch in (1, 2, 3)
        for suffix in ("", "_readiness", "_voiceover_spec", "_subtitles", "_social_copy")
    )
    + tuple(
        f"examples/retail/storefront-web/public/social/pilots/batch{batch:02d}/index.json"
        for batch in (1, 2, 3)
    )
)
PROFILES = {"launch_attribution": ATTRIBUTION, "content_preview": CONTENT}


def encode(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def profile_for(task: dict) -> str:
    text = " ".join(str(task.get(k) or "") for k in ("task_id", "title", "instruction")).lower()
    if task.get("domain") == "research" and "attribution" in text:
        return "launch_attribution"
    if task.get("domain") == "content" and any(k in text for k in ("preview", "pilot")):
        return "content_preview"
    raise ValueError("unsupported_evidence_capability")


def excerpt(raw: bytes, keywords: set[str], name: str = "") -> dict:
    text = raw.decode("utf-8")
    lines = text.splitlines(keepends=True)
    # Keep every pilot script/hook identity as a structured projection instead of
    # picking isolated lines from a large batch JSON document.
    try:
        data = json.loads(text)
    except ValueError:
        data = None
    if isinstance(data, dict) and (
        name.endswith("_subtitles.json") or name.endswith("_social_copy.json")
    ):
        subtitle = name.endswith("_subtitles.json")
        key = "items" if subtitle else "posts"
        projected = {
            "status": data.get("status"),
            "note": str(data.get("note") or "")[:160],
            "guidance": str(data.get("guidance") or "")[:200],
            key: [],
        }
        for item in data.get(key, []):
            if subtitle:
                segments = item.get("segments", [])
                value = {
                    "content_id": item.get("content_id"),
                    "segment_count": len(segments),
                    "end_seconds": segments[-1].get("end") if segments else None,
                    "opening_text": str(segments[0].get("text") or "")[:80] if segments else "",
                }
            else:
                value = {
                    "content_id": item.get("content_id"),
                    "tiktok": {"caption": str(item.get("tiktok", {}).get("caption") or "")[:80]},
                }
            projected[key].append(value)
        return {
            "text": encode(projected).decode(),
            "projection": key,
            "json_paths": [f"$.{key}[*]"],
            "line_ranges": [],
            "complete": False,
            "omission_reason": "subtitle text beyond opening/caption beyond 80 characters; other segments/platforms omitted",
        }
    if (
        isinstance(data, dict)
        and isinstance(data.get("pilots"), list)
        and not name.endswith("_voiceover_spec.json")
    ):
        fields = ("content_id", "hook", "voiceover", "target_duration_seconds", "format", "status")
        projected = {
            "rules": {
                k: data[k]
                for k in ("global_rules", "global_delivery", "audio_contract", "status")
                if k in data
            },
            "pilots": [
                {key: pilot[key] for key in fields if key in pilot}
                for pilot in data["pilots"]
                if isinstance(pilot, dict)
            ],
        }
        rendered = encode(projected).decode()
        if len(rendered.encode()) <= 6000:
            return {
                "text": rendered,
                "projection": "pilots identities/hooks/full voiceover + global rules",
                "json_paths": ["$.global_rules", "$.pilots[*]"],
                "line_ranges": [],
                "complete": False,
                "omission_reason": "non-script fields omitted by fixed JSON projection",
            }
    if len(raw) <= MAX_TEXT_BYTES:
        return {"text": text, "line_ranges": [[1, len(lines)]], "complete": True}
    # Rank whole lines by task vocabulary, with deterministic ties. Preserve source order.
    ranked = sorted(
        range(len(lines)), key=lambda i: (-sum(k in lines[i].lower() for k in keywords), i)
    )
    selected: set[int] = set()
    used = 0
    groups = 0
    for i in ranked:
        if groups >= 4:
            break
        group = [j for j in range(max(0, i - 1), min(len(lines), i + 3)) if j not in selected]
        size = sum(len(f"L{j + 1}: {lines[j]}".encode()) for j in group)
        if size + used <= MAX_TEXT_BYTES:
            selected.update(group)
            used += size
            groups += 1
    ranges = []
    for i in sorted(selected):
        if ranges and ranges[-1][1] == i:
            ranges[-1][1] = i + 1
        else:
            ranges.append([i + 1, i + 1])
    value = "".join(f"L{i + 1}: {lines[i]}" for i in sorted(selected))
    return {
        "text": value,
        "line_ranges": ranges,
        "complete": False,
        "omission_reason": "task_ranked_line_excerpts; unselected lines omitted",
    }


def pack_evidence(task: dict, *, head: str | None, root: Path = ROOT) -> dict:
    profile = profile_for(task)
    words = set(re.findall(r"[a-z][a-z0-9_]{3,}", str(task.get("instruction", "")).lower()))
    keywords = words | {
        "src",
        "cmp",
        "sid",
        "content",
        "session",
        "clickout",
        "naxos",
        "quality",
        "voiceover",
        "status",
    }
    packet = {k: task.get(k) for k in ("task_id", "title", "instruction", "domain", "dependencies")}
    packet.update(
        {
            "head": head,
            "evidence_profile": profile,
            "repository_evidence": [],
            "omitted_sources": [],
            "context_scope": "Repository excerpts only; no live performance or visual inspection. Missing coverage must remain explicit.",
            "limits": {
                "max_prompt_bytes": MAX_PROMPT_BYTES,
                "max_source_bytes": MAX_SOURCE_BYTES,
                "max_text_bytes": MAX_TEXT_BYTES,
            },
        }
    )
    if len(encode(packet)) > 6000:
        raise ValueError("task_metadata_exceeds_context_budget")
    # Fixed priority is authoritative; task-selected profile supplies capability boundary.
    sources = list(PROFILES[profile])
    if profile == "content_preview":
        # All three pilot batches precede optional assets/spec detail; never fill
        # the budget with Batch 01 and silently starve Batches 02/03.
        core_batches = [f"examples/retail/data/scentai_pilot_batch_{b:02d}.json" for b in (1, 2, 3)]
        specs = [
            f"examples/retail/data/scentai_pilot_batch_{b:02d}_voiceover_spec.json"
            for b in (1, 2, 3)
        ]
        sources = (
            core_batches
            + [name for name in sources if name.endswith(("_subtitles.json", "_social_copy.json"))]
            + specs
            + [
                name
                for name in sources
                if name not in core_batches + specs
                and not name.endswith(("_subtitles.json", "_social_copy.json"))
            ]
        )
    for source_index, name in enumerate(sources):
        path = root / name
        reason = None
        if path.is_symlink() or any(p.is_symlink() for p in path.parents if p != root.parent):
            reason = "symlink_disallowed"
        elif not path.is_file():
            reason = "missing"
        elif path.stat().st_size > MAX_SOURCE_BYTES:
            reason = "source_size_limit"
        if reason:
            packet["omitted_sources"].append({"path": name, "reason": reason})
            continue
        raw = path.read_bytes()
        # Fixed public paths still fail closed if secret markers accidentally appear.
        if re.search(
            rb"(?i)(sk-ant-[a-z0-9_-]{16,}|-----BEGIN .*PRIVATE KEY|sb_secret_[a-z0-9_-]+)", raw
        ):
            packet["omitted_sources"].append({"path": name, "reason": "secret_marker"})
            continue
        source = {
            "path": name,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "source_bytes": len(raw),
            **excerpt(raw, keywords, name),
        }
        packet["repository_evidence"].append(source)
        # Reserve room for all remaining omission records; never truncate a serialized prompt.
        reserved = (
            sum(
                len(encode({"path": remaining, "reason": "context_priority_budget"})) + 1
                for remaining in sources[source_index + 1 :]
            )
            + 100
        )
        if len(encode(packet)) > MAX_PROMPT_BYTES - reserved:
            packet["repository_evidence"].pop()
            packet["omitted_sources"].append({"path": name, "reason": "context_priority_budget"})
    if len(encode(packet)) > MAX_PROMPT_BYTES:
        raise ValueError("evidence_packet_exceeds_context_budget")
    packet["packet_sha256"] = hashlib.sha256(encode(packet)).hexdigest()
    if len(encode(packet)) > MAX_PROMPT_BYTES:
        raise ValueError("evidence_packet_exceeds_context_budget")
    return packet
