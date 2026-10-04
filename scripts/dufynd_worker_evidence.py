"""Deterministic public-repository evidence; no tools, provider calls or arbitrary paths."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_PROMPT_BYTES = 24576
MAX_SOURCE_BYTES = 262144
MAX_TEXT_BYTES = 500

ATTRIBUTION = (
    "examples/retail/storefront-web/lib/analytics.ts",
    "examples/retail/storefront-web/components/AcquisitionLanding.tsx",
    "examples/retail/storefront-web/app/duft/[slug]/page.tsx",
    "examples/retail/storefront-web/app/vergleich/[pair]/page.tsx",
    "examples/retail/api/merchant_partners.py",
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
        "examples/retail/data/dufynd_high_end_launch_review.json",
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


CODE_WINDOWS = {
    "examples/retail/api/tests/test_clickout_analytics_correlation.py": [
        ('sid=" session-partner', 6, 2),
        ('"campaign_id": "launch_01"', 6, 2),
        ('sid=" session-offer', 6, 2),
        ('"session_id": "session-offer', 2, 9),
    ],
    ATTRIBUTION[0]: [
        ("export function rememberAcquisitionAttribution", 0, 33),
        ("export function appendAcquisitionAttribution", 0, 36),
        ("export async function ensureAnalyticsSession", 0, 34),
        ("window.sessionStorage.getItem", 2, 8),
    ],
    "examples/retail/storefront-web/components/AcquisitionAnalytics.tsx": [
        ("const params = new URLSearchParams", 0, 35)
    ],
    "examples/retail/storefront-web/components/AcquisitionInternalLink.tsx": [
        ("useEffect(() =>", 0, 17)
    ],
    "examples/retail/storefront-web/components/AcquisitionLanding.tsx": [
        ("<AcquisitionAnalytics", 0, 12)
    ],
    "examples/retail/storefront-web/app/duft/[slug]/page.tsx": [
        ("<AcquisitionAnalytics", 0, 4),
        ("<FragranceOffers", 0, 9),
        ("<AcquisitionInternalLink", 0, 6),
    ],
    "examples/retail/storefront-web/app/vergleich/[pair]/page.tsx": [
        ("<AcquisitionAnalytics", 0, 9),
        ("<FragranceOffers", 0, 13),
    ],
    "examples/retail/storefront-web/components/ComparisonAnalytics.tsx": [
        ("useEffect(() =>", 0, 25)
    ],
    "examples/retail/storefront-web/components/FragranceOffers.tsx": [
        ("ensureAnalyticsSession().finally", 2, 10),
        ("href={appendAcquisitionAttribution", 2, 11),
    ],
    "examples/retail/storefront-web/lib/api.ts": [
        ("export async function initializeAnalyticsSession", 0, 20),
        ("export function merchantClickoutUrl", 0, 5),
    ],
    "examples/retail/api/main.py": [
        ("async def merchant_clickout(", 1, 44),
        ("async def analytics_event(", 1, 17),
        ("target = partner_clickout_url(", 0, 11),
    ],
    "examples/retail/api/merchant_offers.py": [
        ("def offer_clickout_target(", 0, 7),
        ("def customer_offer_payload(", 0, 20),
    ],
    "examples/retail/api/merchant_partners.py": [("def partner_clickout_url(", 0, 28)],
    "examples/retail/api/analytics.py": [("def session_key(", 0, 40)],
    "docs/dufynd_creative_learning_library.md": [("## Example 38", 0, 12)],
}


def content_projection(name: str, data: dict) -> dict | None:
    """Fixed JSON fields; no live metrics, scores or inferred audiovisual quality."""

    def fields(value, names):
        return {k: value[k] for k in names if k in value}

    if name.endswith("_subtitles.json"):
        return {
            "status": data.get("status"),
            "items": [
                {
                    "content_id": item.get("content_id"),
                    "segment_count": len(item.get("segments", [])),
                    "opening_text": str(item.get("segments", [{}])[0].get("text", ""))[:40],
                    "end_seconds": item.get("segments", [{}])[-1].get("end"),
                }
                for item in data.get("items", [])
            ],
        }
    if name.endswith("_social_copy.json"):
        return {
            "posts": [
                {
                    "content_id": p.get("content_id"),
                    "tiktok": {"caption": str(p.get("tiktok", {}).get("caption", ""))[:80]},
                }
                for p in data.get("posts", [])
            ]
        }
    if name.endswith("_voiceover_spec.json"):
        return {
            "status": data.get("status"),
            "audio_contract": fields(data.get("audio_contract", {}), ("duration_rule",)),
            "pilots": [
                fields(p, ("content_id", "word_count", "required_wpm"))
                for p in data.get("pilots", [])
            ],
        }
    if "/social/pilots/" in name and name.endswith("index.json"):
        return {
            "previews": [
                fields(p, ("content_id", "audio", "status")) for p in data.get("previews", [])
            ]
        }
    if name.endswith("dufynd_high_end_launch_assets.json"):
        return {
            "status": data.get("status"),
            "automatic_publish_allowed": data.get("automatic_publish_allowed"),
            "assets": [
                fields(p, ("content_id", "asset_state", "creative_state"))
                for p in data.get("assets", [])
            ],
            "rebuild_required": [
                fields(p, ("content_id", "status")) for p in data.get("rebuild_required", [])
            ],
        }
    if name.endswith("dufynd_high_end_launch_review.json"):
        return fields(
            data,
            (
                "state",
                "automatic_publish_allowed",
                "paid_generation_authorized",
                "quality_floor",
                "rebuild_exclusions",
            ),
        )
    if name.endswith("scentai_content_pipeline_status.json"):
        return fields(
            data,
            (
                "pipeline_state",
                "active_track",
                "legacy_pilot_batches",
                "total_pilots",
                "next_action",
                "next_action_class",
            ),
        )
    if name.endswith("dufynd_content_strategy.json"):
        return fields(
            data,
            (
                "strategy_status",
                "legacy_pilot_role",
                "next_action",
                "next_action_class",
                "approval_gates",
            ),
        )
    if name.endswith("dufynd_content_buffer_plan.json"):
        return {
            **fields(data, ("status", "next_no_spend_completion")),
            "inventory_snapshot": fields(
                data.get("inventory_snapshot", {}),
                ("planned_core_creatives", "preview_ready_creatives", "final_video_renders_ready"),
            ),
        }
    if name.endswith("dufynd_high_end_pre_publish_checklist.json"):
        return {
            **fields(data, ("state", "automatic_publish_allowed", "paid_generation_required")),
            "copy_qc": fields(data.get("copy_qc", {}), ("status", "rules", "cta_rule")),
        }
    return None


def compact_projection(data: dict) -> dict:
    result = {}
    for key, value in data.items():
        if isinstance(value, list) and value and all(isinstance(row, dict) for row in value):
            columns = list(dict.fromkeys(k for row in value for k in row))
            result[key] = {
                "columns": columns,
                "rows": [[row.get(k) for k in columns] for row in value],
            }
        else:
            result[key] = value
    return result


def projection_rows(source: dict, key: str) -> list[dict]:
    value = source["data"].get(key, [])
    if isinstance(value, list):
        return value
    return [dict(zip(value["columns"], row, strict=True)) for row in value["rows"]]


def source_text(source: dict) -> str:
    return source.get("text") or encode(source.get("data", {})).decode()


def excerpt(raw: bytes, keywords: set[str], name: str = "") -> dict:
    text = raw.decode("utf-8")
    lines = text.splitlines(keepends=True)
    # Keep every pilot script/hook identity as a structured projection instead of
    # picking isolated lines from a large batch JSON document.
    try:
        data = json.loads(text)
    except ValueError:
        data = None
    if name in CODE_WINDOWS:
        selected = set()
        missing = []
        for marker, before, after in CODE_WINDOWS[name]:
            matches = [i for i, line in enumerate(lines) if marker in line]
            if not matches:
                missing.append(marker)
                continue
            i = matches[0]
            selected.update(range(max(0, i - before), min(len(lines), i + after + 1)))
        ranges = []
        for i in sorted(selected):
            if ranges and ranges[-1][1] == i:
                ranges[-1][1] = i + 1
            else:
                ranges.append([i + 1, i + 1])
        return {
            "text": "".join(lines[i] for i in sorted(selected)),
            "line_ranges": ranges,
            "complete": False,
            "missing_anchors": missing,
            "omission_reason": "code_windows_only",
        }
    if isinstance(data, dict):
        projection = content_projection(name, data)
        if projection is not None:
            return {
                "data": compact_projection(projection),
                "projection": "fields",
                "complete": False,
                "omission_reason": "projection_fields_only",
            }
    if (
        isinstance(data, dict)
        and isinstance(data.get("pilots"), list)
        and not name.endswith("_voiceover_spec.json")
    ):
        fields = ("content_id", "hook", "voiceover", "target_duration_seconds")
        projected = {
            "rules": {
                "global_rules": {
                    k: v
                    for k, v in data.get("global_rules", {}).items()
                    if k in ("claims_policy", "ranking_policy")
                }
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
                "data": compact_projection(projected),
                "projection": "pilots_fields",
                "complete": False,
                "omission_reason": "unselected fields omitted",
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
    if profile == "content_preview":
        essential = [
            n
            for n in sources
            if n.endswith(("_subtitles.json", "_social_copy.json", "_voiceover_spec.json"))
        ]
        strategic = [
            "docs/dufynd_creative_learning_library.md",
            *CONTENT[:6],
            "examples/retail/data/dufynd_high_end_pre_publish_checklist.json",
        ]
        indexes = [n for n in sources if "/social/pilots/" in n]
        sources = list(dict.fromkeys(core_batches + essential + strategic + indexes + sources))
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
            "priority": source_index + 1,
            **excerpt(raw, keywords, name),
        }
        if "data" in source:
            source.pop("projection", None)
            source.pop("complete", None)
        if source.get("missing_anchors") == []:
            source.pop("missing_anchors")
        packet["repository_evidence"].append(source)
        # Reserve room for all remaining omission records; never truncate a serialized prompt.
        reserved = (
            sum(
                len(
                    encode(
                        {
                            "path": remaining,
                            "reason": "context_priority_budget",
                            "priority": 99,
                        }
                    )
                )
                + 1
                for remaining in sources[source_index + 1 :]
            )
            + 100
        )
        if len(encode(packet)) > MAX_PROMPT_BYTES - reserved:
            packet["repository_evidence"].pop()
            packet["omitted_sources"].append(
                {
                    "path": name,
                    "priority": source_index + 1,
                    "reason": "context_priority_budget",
                }
            )
    if len(encode(packet)) > MAX_PROMPT_BYTES:
        raise ValueError("evidence_packet_exceeds_context_budget")
    packet["packet_sha256"] = hashlib.sha256(encode(packet)).hexdigest()
    if len(encode(packet)) > MAX_PROMPT_BYTES:
        raise ValueError("evidence_packet_exceeds_context_budget")
    return packet
