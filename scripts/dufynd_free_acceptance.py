"""Read-only pack audit and bounded OFFLINE fixture lifecycle. Never a provider adapter.

The checker below accepts only exact cited repository facts in structured test
fixtures. It cannot semantically approve arbitrary prose or production Maker output.
No Supabase writes, HTTP, provider client, queue dispatch or spend authorization.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from scripts.dufynd_independent_checker import (
    CheckerIdentity,
    make_handoff,
    next_safe_task,
    run_checker,
)
from scripts.dufynd_worker_evidence import (
    ATTRIBUTION,
    CONTENT,
    ROOT,
    encode,
    pack_evidence,
    projection_rows,
    source_text,
)

TASK_IDS = (
    "jarvis_launch_attribution_posttech_audit_20261001",
    "jarvis_content_preview_priority_20261001",
)
PREFIX = "examples/retail/storefront-web/"
STAGES = {
    "acquisition_landing": (
        PREFIX + "components/AcquisitionLanding.tsx",
        ("<AcquisitionAnalytics", "<AcquisitionInternalLink"),
    ),
    "landing_parameters": (
        PREFIX + "components/AcquisitionAnalytics.tsx",
        ('params.get("src")', 'params.get("cmp")', 'params.get("content")'),
    ),
    "persistence": (
        PREFIX + "lib/analytics.ts",
        ("sessionStorage.setItem", "sessionStorage.getItem"),
    ),
    "session": (PREFIX + "lib/analytics.ts", ("ensureAnalyticsSession", 'searchParams.set("sid"')),
    "product_detail": (
        PREFIX + "app/duft/[slug]/page.tsx",
        ("<AcquisitionAnalytics", "<FragranceOffers"),
    ),
    "comparison": (
        PREFIX + "app/vergleich/[pair]/page.tsx",
        ("<ComparisonAnalytics", "<FragranceOffers"),
    ),
    "offer_link": (
        PREFIX + "components/FragranceOffers.tsx",
        ("ensureAnalyticsSession", "appendAcquisitionAttribution", "merchantClickoutUrl"),
    ),
    "merchant_clickout": (
        "examples/retail/api/main.py",
        (
            "async def merchant_clickout",
            "sanitize_attribution_identifier(sid)",
            "RedirectResponse(url=target",
        ),
    ),
    "tracking_url": (
        "examples/retail/api/merchant_partners.py",
        ("def partner_clickout_url", 'query.append(("clickref", clickref))', "urlencode(query)"),
    ),
    "offer_target": (
        "examples/retail/api/merchant_offers.py",
        ("def offer_clickout_target", "offer.affiliate_url", '"clickout_path"'),
    ),
    "server_analytics": (
        "examples/retail/api/main.py",
        ("analytics_tracker.record", 'event="merchant_clickout"', "async def analytics_event"),
    ),
    "tests": (
        "examples/retail/api/tests/test_clickout_analytics_correlation.py",
        ("sid", "campaign_id"),
    ),
}
CONTENT_ESSENTIAL = {
    "learning": "docs/dufynd_creative_learning_library.md",
    "quality_floor": "examples/retail/data/dufynd_high_end_launch_review.json",
    "assets": "examples/retail/data/dufynd_high_end_launch_assets.json",
    "pipeline": "examples/retail/data/scentai_content_pipeline_status.json",
    "buffer": "examples/retail/data/dufynd_content_buffer_plan.json",
    "strategy": "examples/retail/data/dufynd_content_strategy.json",
    "qa": "examples/retail/data/dufynd_high_end_pre_publish_checklist.json",
}


def digest(value: dict) -> str:
    return hashlib.sha256(encode(value)).hexdigest()


def coverage(packet: dict) -> dict:
    sources = {s["path"]: s for s in packet["repository_evidence"]}
    if packet["evidence_profile"] == "launch_attribution":
        return {
            stage: path in sources
            and all(needle in source_text(sources[path]) for needle in needles)
            for stage, (path, needles) in STAGES.items()
        }
    checks = {
        family: path in sources and bool(source_text(sources[path]))
        for family, path in CONTENT_ESSENTIAL.items()
    }
    for batch in (1, 2, 3):
        for suffix in ("", "_voiceover_spec", "_subtitles", "_social_copy"):
            path = f"examples/retail/data/scentai_pilot_batch_{batch:02d}{suffix}.json"
            source = sources.get(path)
            key = (
                "pilots"
                if suffix in ("", "_voiceover_spec")
                else "items"
                if suffix == "_subtitles"
                else "posts"
            )
            checks[f"batch{batch}{suffix or '_scripts'}"] = bool(
                source and len(projection_rows(source, key)) == 5
            )
        index = f"examples/retail/storefront-web/public/social/pilots/batch{batch:02d}/index.json"
        checks[f"batch{batch}_preview_inventory"] = (
            index in sources and len(projection_rows(sources[index], "previews")) == 5
        )
    return checks


class FixtureChecker:
    """Independent deterministic test checker; NOT natural-language semantic verification."""

    def __init__(self, root: Path = ROOT):
        self.root = root
        self.calls = 0

    def review(self, handoff: dict) -> dict:
        self.calls += 1
        packet = handoff["evidence"]
        result = json.loads(handoff["maker_result"])
        sources = {s["path"]: s for s in packet["repository_evidence"]}
        provenance = packet.get("packet_sha256") == digest(
            {k: v for k, v in packet.items() if k != "packet_sha256"}
        )
        expected = pack_evidence(handoff["task"], head=packet["head"], root=self.root)
        expected_sources = {s["path"]: s for s in expected["repository_evidence"]}
        for path, source in sources.items():
            provenance &= path in set(ATTRIBUTION + CONTENT) and source == expected_sources.get(
                path
            )
        supported = bool(result.get("claims"))
        for claim in result.get("claims", []):
            citation = claim.get("citation", {})
            source = sources.get(citation.get("path"))
            supported &= bool(
                source
                and claim.get("kind") == "verbatim_repository_fact"
                and claim.get("assertion") == citation.get("quote")
                and citation.get("quote")
                and citation["quote"] in source_text(source)
                and citation.get("sha256") == source["sha256"]
            )
        complete = all(coverage(packet).values())
        candidates = result.get("candidate_ids", [])
        scope = (
            result.get("kind") == "offline_fixture"
            and result.get("task_id") == handoff["task"]["task_id"]
        )
        if handoff["task"]["domain"] == "content":
            pilots = [
                p["content_id"]
                for s in sources.values()
                if "data" in s
                and "pilots" in s["data"]
                and "hook" in projection_rows(s, "pilots")[0]
                for p in projection_rows(s, "pilots")
            ]
            scope &= (
                1 <= len(candidates) <= 3
                and len(set(candidates)) == len(candidates)
                and all(c in pilots for c in candidates)
            )
            scope &= not any(c in {"sillage_haltbarkeit_01", "edp_vs_edt_01"} for c in candidates)
        safety = result.get("limitations") == [
            "repository_only",
            "no_visual_quality_claim",
            "no_live_performance_claim",
            "no_publish_approval",
        ]
        actions = result.get("requested_actions") == []
        checks = {
            "fact_fidelity": bool(provenance and supported),
            "unsupported_claims": bool(supported),
            "hallucinations": bool(supported),
            "completeness": complete,
            "task_scope": bool(scope),
            "safety": safety,
            "spend": actions,
            "publishing": actions,
            "external_actions": actions,
            "evidence_coverage": complete,
        }
        outcome = (
            "needs_more_evidence"
            if not complete or not provenance
            else "verified"
            if all(checks.values())
            else "rework_required"
        )
        return {
            "handoff_sha256": handoff["handoff_sha256"],
            "outcome": outcome,
            "checks": checks,
            "additional_evidence": []
            if outcome == "verified"
            else ["missing coverage/provenance or unsupported fixture claim"],
        }


def maker_fixture(task: dict, packet: dict) -> str:
    """Deterministic citation fixture, not a claim of model reasoning or actual candidate quality."""
    claims = []
    candidates = []
    if task["domain"] == "research":
        for _, (path, needles) in STAGES.items():
            source = next(s for s in packet["repository_evidence"] if s["path"] == path)
            quote = needles[0]
            claims.append(
                {
                    "kind": "verbatim_repository_fact",
                    "assertion": quote,
                    "citation": {"path": path, "quote": quote, "sha256": source["sha256"]},
                }
            )
    else:
        for source in packet["repository_evidence"]:
            if (
                "data" in source
                and "pilots" in source["data"]
                and "hook" in projection_rows(source, "pilots")[0]
            ):
                pilot = projection_rows(source, "pilots")[0]
                candidates.append(pilot["content_id"])
                quote = pilot["hook"]
                # Canonical serialized projection escapes quotes; cite an exact serialized fragment.
                quote = encode(quote).decode()
                claims.append(
                    {
                        "kind": "verbatim_repository_fact",
                        "assertion": quote,
                        "citation": {
                            "path": source["path"],
                            "quote": quote,
                            "sha256": source["sha256"],
                        },
                    }
                )
    return encode(
        {
            "kind": "offline_fixture",
            "task_id": task["task_id"],
            "claims": claims,
            "candidate_ids": candidates,
            "requested_actions": [],
            "limitations": [
                "repository_only",
                "no_visual_quality_claim",
                "no_live_performance_claim",
                "no_publish_approval",
            ],
        }
    ).decode()


def simulate(task: dict, packet: dict, tasks: list[dict], *, output: str | None = None) -> dict:
    checker = FixtureChecker()
    handoff = make_handoff(
        task,
        output or maker_fixture(task, packet),
        packet,
        maker="offline-maker-fixture",
        runtime={
            "budget_id": "jarvis_nightshift_mini_canary_20261004_002",
            "cost_usd": "0",
            "reservation_id": None,
            "simulation": True,
        },
    )
    receipt = run_checker(
        handoff, checker, identity=CheckerIdentity("offline-independent-citation-checker")
    )
    local = copy.deepcopy(tasks)
    # Only local fixture copies. Independent host receipt is the sole transition input.
    for row in local:
        if row["task_id"] == task["task_id"]:
            row["status"] = receipt["next_state"]
    proposed = next_safe_task(local, task["task_id"], receipt)
    terminal = {
        "task_id": task["task_id"],
        "state": receipt["next_state"],
        "verification_receipt_sha256": receipt["receipt_sha256"],
        "next_safe_task": proposed["task_id"] if proposed else None,
        "dispatch_allowed": False,
        "paid_calls": 0,
        "cost_usd": "0",
        "checker_invocations": checker.calls,
        "automatic_paid_retry": False,
        "publishing_allowed": False,
        "simulation": True,
    }
    terminal["terminal_sha256"] = digest(terminal)
    return {"handoff": handoff, "receipt": receipt, "terminal": terminal}


def audit(task: dict, packet: dict) -> dict:
    from scripts.dufynd_anthropic_counted import input_body

    priorities = {s["path"]: s["priority"] for s in packet["repository_evidence"]}
    priorities.update({s["path"]: s.get("priority") for s in packet["omitted_sources"]})
    all_paths = list(
        dict.fromkeys(
            [s["path"] for s in packet["repository_evidence"] + packet["omitted_sources"]]
        )
    )
    records = []
    for path in all_paths:
        source = next((s for s in packet["repository_evidence"] if s["path"] == path), None)
        raw = (ROOT / path).read_bytes() if (ROOT / path).is_file() else None
        records.append(
            {
                "path": path,
                "priority": priorities[path],
                "included": source is not None,
                "sha256": hashlib.sha256(raw).hexdigest() if raw is not None else None,
                "source_bytes": len(raw) if raw is not None else None,
                "provided_bytes": len(source_text(source).encode()) if source else 0,
                "estimated_tokens_utf8_div_4": (len(source_text(source).encode()) + 3) // 4
                if source
                else 0,
                "line_ranges": source.get("line_ranges") if source else None,
                "projection": list(source["data"]) if source and "data" in source else None,
                "omission_reason": source.get("omission_reason")
                if source
                else next(s["reason"] for s in packet["omitted_sources"] if s["path"] == path),
            }
        )
    size = len(encode(packet))
    return {
        "task_id": task["task_id"],
        "head": packet["head"],
        "packet_sha256": packet["packet_sha256"],
        "prompt_sha256": hashlib.sha256(encode(packet)).hexdigest(),
        "prompt_bytes": size,
        "estimated_tokens": {
            "heuristic_utf8_bytes_div_4": (size + 3) // 4,
            "count_input_body_bytes": len(encode(input_body(encode(packet).decode()))),
            "not_official_anthropic_count": True,
        },
        "coverage": coverage(packet),
        "sources": records,
    }


def failure_fixture(task: dict, *, head: str | None = None) -> dict:
    """Exercise the real counted failure handler; every provider method is disabled."""
    import asyncio
    from unittest.mock import patch

    from scripts import dufynd_anthropic_counted as counted

    class Bridge:
        def __init__(self):
            self.records, self.master, self.updates = [], {}, []

        def load_autonomy_queue(self):
            return {"safe_to_execute": [task]}

        def claim_worker(self, *_):
            return task | {"worker_owner": "offline-fixture", "lease_token": "offline-fixture"}

        def record_run(self, **kwargs):
            self.records.append(kwargs)

        def upsert_master_status(self, *, key, category, value):
            self.master[key] = value

        def update_worker(self, *args, **kwargs):
            self.updates.append((args, kwargs))

    class DisabledProvider(counted.CountedClient):
        def count(self, _):
            self.last_count = 6452  # fixture estimate; NOT a provider measurement
            return self.last_count

        def _post(self, *_):
            raise AssertionError("provider HTTP disabled")

        def execute(self, *_args, **_kwargs):
            raise AssertionError("paid dispatch disabled")

    bridge = Bridge()
    with (
        patch.object(
            counted,
            "resolve_budget",
            return_value=("jarvis_nightshift_mini_canary_20261004_002", {}),
        ),
        patch.object(counted, "CountedClient", DisabledProvider),
        patch.dict(
            "os.environ",
            {
                "ANTHROPIC_API_KEY": "offline-fixture",
                "GITHUB_SHA": head or "offline-fixture",
                "GITHUB_RUN_ID": "offline-fixture",
                "GITHUB_RUN_ATTEMPT": "1",
            },
        ),
    ):
        result_code = asyncio.run(counted.process_counted_task(bridge, task_id=task["task_id"]))
    receipt = bridge.master[f"jarvis.failure_receipt.{task['task_id']}"]
    return {
        "simulation": True,
        "result_code": result_code,
        "fixture_token_count": 6452,
        "actual_provider_calls": 0,
        "receipt": receipt,
        "task_updates": len(bridge.updates),
        "run_type": bridge.records[0]["run_type"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    tasks = json.loads(args.tasks.read_text())
    if {t["task_id"] for t in tasks} != set(TASK_IDS) or len(tasks) != 2:
        raise ValueError("exact_real_tasks_required")
    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    args.output.joinpath("failure-receipt.json").write_text(
        json.dumps(failure_fixture(tasks[0], head=args.head), indent=2)
    )
    for task in tasks:
        from scripts.dufynd_anthropic_counted import input_body

        packet = pack_evidence(task, head=args.head)
        prefix = "attribution" if task["domain"] == "research" else "content"
        args.output.joinpath(prefix + "-context.json").write_bytes(encode(packet))
        args.output.joinpath(prefix + "-count-input.json").write_bytes(
            encode(input_body(encode(packet).decode()))
        )
        report = audit(task, packet)
        args.output.joinpath(prefix + "-audit.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2)
        )
        simulation = simulate(task, packet, tasks)
        args.output.joinpath(prefix + "-lifecycle.json").write_text(
            json.dumps(simulation, ensure_ascii=False, indent=2)
        )
        results.append(
            {
                "task_id": task["task_id"],
                "coverage": all(report["coverage"].values()),
                "fixture_verified": simulation["receipt"]["outcome"] == "verified",
            }
        )
    args.output.joinpath("summary.json").write_text(
        json.dumps({"head": args.head, "paid_calls": 0, "results": results}, indent=2)
    )
    return 0 if all(r["coverage"] and r["fixture_verified"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
