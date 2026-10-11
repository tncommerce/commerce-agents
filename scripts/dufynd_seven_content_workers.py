"""DUFYND's zero-provider-cost seven-role editorial packet runtime.

These are distinct deterministic *validation, selection and handoff* workers.
They do not generate images, call language models, claim Supabase worker leases,
or publish posts. Supabase source is read-only. A role is DONE only when its
actual bounded input is checked; unavailable creativity or evidence is held.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ROLE_ORDER = ("W1", "W3", "W4", "W5", "W6", "W2", "W7")
DEPENDENCIES = {
    "W1": (),
    "W3": ("W1",),
    "W4": ("W1",),
    "W5": ("W1", "W3"),
    "W6": ("W1", "W3", "W5"),
    "W2": ("W1", "W3", "W4", "W5", "W6"),
    "W7": ("W1", "W2", "W3", "W4", "W5", "W6"),
}
ROLE_NAMES = {
    "W1": "Growth Blueprint",
    "W2": "Viral Instagram Writer",
    "W3": "Audience Magnet Analyzer",
    "W4": "Authority Builder",
    "W5": "Engagement Loop Creator",
    "W6": "Emotional Hook Generator",
    "W7": "30-Day Content Calendar",
}
SUCCESS_STATES = {"DONE", "DONE_WITH_HOLDS"}
SCHEMA_VERSION = 1


class WorkerInputError(ValueError):
    """An invalid or mismatched packet must not be retried as a new round."""


def digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def normalized(value: object) -> str:
    value = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"[^\w]+", " ", value, flags=re.UNICODE).strip()


def valid_source_url(value: object) -> bool:
    try:
        parts = urlsplit(str(value))
        return (
            parts.scheme == "https"
            and bool(parts.hostname)
            and parts.username is None
            and parts.password is None
            and len(str(value)) <= 2048
        )
    except ValueError:
        return False


def rows(section: dict[str, Any], field: str) -> list[Any]:
    value = section.get(field)
    return value if isinstance(value, list) else []


def unique_text(items: list[Any], minimum: int, maximum: int) -> list[str]:
    selected: list[str] = []
    seen: set[str] = set()
    for value in items[:maximum]:
        if not isinstance(value, str) or len(value.strip()) < 8:
            continue
        key = normalized(value)
        if key and key not in seen:
            selected.append(value.strip())
            seen.add(key)
    return selected if len(selected) >= minimum else []


def packet(state: str, output: dict[str, Any], holds: list[str] | None = None) -> dict:
    holds = list(holds or [])
    if state == "DONE" and holds:
        state = "DONE_WITH_HOLDS"
    return {"state": state, "output": output, "holds": holds, "cost_eur": 0}


def growth_blueprint(section: dict, _prior: dict, _existing: dict) -> dict:
    expected = ("audience", "voice", "channels", "goals", "cadence_test_mix")
    if not all(section.get(field) for field in expected):
        return packet("BLOCKED", {}, ["growth_blueprint_input_incomplete"])
    mix = section["cadence_test_mix"]
    if (
        not isinstance(mix, dict)
        or set(mix) != {"meme", "carousel", "reel", "slideshow"}
        or any(type(x) is not int or x < 0 for x in mix.values())
        or sum(mix.values()) != 30
    ):
        return packet("BLOCKED", {}, ["invalid_30_day_test_mix"])
    return packet(
        "DONE",
        {
            "audience": str(section["audience"]),
            "voice": str(section["voice"]),
            "channel_hypothesis": str(section["channels"]),
            "objectives": list(section["goals"])[:8],
            "test_mix_not_a_posting_quota": mix,
            "observations_from_prior_editorial_source": str(section.get("observations", "")),
            "originality_goal": "broader relatable reactions; verify against real metrics",
        },
    )


def audience_magnet(section: dict, _prior: dict, _existing: dict) -> dict:
    patterns = []
    seen = set()
    for item in rows(section, "patterns")[:30]:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        try:
            date.fromisoformat(str(item.get("date", "")))
        except ValueError:
            continue
        if not valid_source_url(url) or url in seen:
            continue
        mechanism = str(item.get("mechanic") or "").strip()
        if not mechanism:
            continue
        seen.add(url)
        patterns.append(
            {
                "url": url,
                "source_date": item["date"],
                "mechanism": mechanism,
                "fresh_page_verification": "NOT_PERFORMED_BY_OFFLINE_WORKER",
                "viral_outcome_claim": False,
            }
        )
    if not patterns:
        return packet("BLOCKED", {}, ["no_dated_valid_pattern_sources"])
    return packet(
        "DONE_WITH_HOLDS",
        {"reference_mechanics": patterns, "comparison": "evidence_leads_only"},
        ["fresh_creator_metrics_and_source_verification_unavailable_offline"],
    )


def authority_builder(section: dict, _prior: dict, _existing: dict) -> dict:
    candidates = []
    seen = set()
    for item in rows(section, "insights")[:15]:
        if not isinstance(item, dict):
            continue
        url, claim = item.get("source_url"), str(item.get("claim") or "").strip()
        key = normalized(claim)
        if not valid_source_url(url) or not key or key in seen:
            continue
        seen.add(key)
        candidates.append(
            {
                "id": str(item.get("id") or ""),
                "theme": str(item.get("theme") or ""),
                "draft_claim": claim,
                "source_url": url,
                "facts_cleared_for_publication": False,
                "source_verification": "RECHECK_REQUIRED",
                "sku_claims_allowed": False,
            }
        )
    if len(candidates) < 5:
        return packet("BLOCKED", {}, ["five_independent_sourced_insights_missing"])
    return packet(
        "DONE_WITH_HOLDS",
        {"fact_candidates": candidates[:5]},
        ["no_live_page_fetch_or_qualified_exact_claim_verification"],
    )


def engagement_loop(section: dict, _prior: dict, _existing: dict) -> dict:
    questions = unique_text(rows(section, "questions"), 10, 30)
    if not questions or any("?" not in question for question in questions[:10]):
        return packet("BLOCKED", {}, ["ten_specific_questions_missing"])
    return packet("DONE", {"questions": questions[:10], "proven_replies": False})


def emotional_hooks(section: dict, _prior: dict, _existing: dict) -> dict:
    hooks = unique_text(rows(section, "hooks"), 20, 45)
    if not hooks:
        return packet("BLOCKED", {}, ["twenty_distinct_hooks_missing"])
    return packet("DONE", {"hooks": hooks[:20], "measured_hook_success": False})


def viral_writer(section: dict, prior: dict, existing: dict) -> dict:
    hooks = set(prior["W6"]["output"]["hooks"])
    questions = set(prior["W5"]["output"]["questions"])
    frozen = {normalized(s) for s in existing.get("frozen_titles", [])}
    published = {normalized(s) for s in existing.get("published_titles", [])}
    proposals: list[dict] = []
    seen = set()
    for item in rows(section, "ideas")[:25]:
        if not isinstance(item, dict):
            continue
        uid = str(item.get("id") or "")
        title = str(item.get("title") or "")
        hook = str(item.get("hook") or "")
        if not uid or not title or not hook or uid in seen:
            continue
        seen.add(uid)
        warnings = []
        if normalized(title) in frozen | published:
            warnings.append("existing_frozen_or_published_creative")
        if hook not in hooks:
            warnings.append("hook_not_matched_to_W6")
        if item.get("question") not in questions:
            warnings.append("question_not_matched_to_W5")
        overlap = str(item.get("overlap") or "")
        if "hold" in overlap or "facts_gated" in overlap:
            warnings.append("manual_similarity_or_fact_review")
        proposals.append(
            {
                "id": uid,
                "title": title,
                "hook": hook,
                "format": str(item.get("format") or ""),
                "concept": str(item.get("concept") or ""),
                "community_question": str(item.get("question") or ""),
                "source_status": "EDITORIALLY_PREPARED_NOT_AUTONOMOUSLY_GENERATED",
                "asset_created": False,
                "visual_score": None,
                "creative_approval": False,
                "publication_approval": False,
                "review_holds": warnings,
            }
        )
    if len(proposals) < 10:
        return packet("BLOCKED", {"ideas": proposals}, ["ten_distinct_idea_inputs_missing"])
    broken = [
        p["id"]
        for p in proposals
        if any(
            h in p["review_holds"] for h in ("hook_not_matched_to_W6", "question_not_matched_to_W5")
        )
    ]
    if broken:
        return packet(
            "BLOCKED",
            {"ideas": proposals, "broken_crosslink_ids": broken},
            ["exact_W5_W6_crosslinks_required"],
        )
    holds = ["visual_and_owner_creative_qa_pending", "worker_is_not_an_inference_provider"]
    return packet(
        "DONE_WITH_HOLDS",
        {
            "ideas": proposals[:10],
            "editorial_shortlist": [p for p in proposals if not p["review_holds"]][:3],
        },
        holds,
    )


def is_placeholder_hook(value: str) -> bool:
    text = normalized(value)
    return (
        not text
        or text in {"tbd", "todo", "pending", "placeholder", "platzhalter"}
        or any(
            fragment in text
            for fragment in (
                "preserve frozen original text",
                "draft a distinct hook",
                "hook folgt",
                "hook später",
                "insert hook",
                "lorem ipsum",
            )
        )
    )


def thirty_day_calendar(section: dict, _prior: dict, existing: dict) -> dict:
    calendar = rows(section, "calendar")
    if len(calendar) != 30:
        return packet("BLOCKED", {}, ["thirty_daily_editorial_slots_missing"])
    unique = set()
    output = []
    incomplete_hook_dates: list[str] = []
    frozen_reference_holds: list[str] = []
    reservations = existing.get("reserved", {})
    if not isinstance(reservations, dict):
        return packet("BLOCKED", {}, ["invalid_existing_reservation_map"])
    for item in calendar:
        if not isinstance(item, dict):
            return packet("BLOCKED", {}, ["malformed_calendar_slot"])
        try:
            slot_date = date.fromisoformat(str(item.get("date")))
        except ValueError:
            return packet("BLOCKED", {}, ["invalid_calendar_date"])
        key = slot_date.isoformat()
        if key in unique:
            return packet("BLOCKED", {}, ["duplicate_calendar_day"])
        unique.add(key)
        title = str(item.get("idea") or "").strip()
        hook = str(item.get("hook") or "").strip()
        reference = item.get("frozen_ref")
        frozen = (
            (existing.get("frozen_refs") or {}).get(reference)
            if isinstance(reference, str)
            else None
        )
        reference_only = bool(item.get("reference_only"))
        if reference_only:
            if (
                not isinstance(frozen, dict)
                or not re.fullmatch(r"[a-f0-9]{64}", str(item.get("frozen_sha256") or ""))
                or frozen.get("record_sha256") != item.get("frozen_sha256")
            ):
                return packet("BLOCKED", {}, ["invalid_frozen_reference:" + key])
            if hook:
                return packet("BLOCKED", {}, ["reference_only_must_not_rewrite_frozen_hook:" + key])
            frozen_reference_holds.append(key)
        if not title or (not hook and not reference_only):
            return packet("BLOCKED", {}, ["empty_calendar_idea_or_hook"])
        if not reference_only and is_placeholder_hook(hook):
            incomplete_hook_dates.append(key)
        if key in reservations and normalized(str(reservations[key])) not in normalized(title):
            return packet("BLOCKED", {}, ["reserved_owner_final_cannot_be_replaced:" + key])
        output.append(
            {
                "date": key,
                "idea": title,
                "hook": hook,
                "format": str(item.get("format") or ""),
                "gate_from_prior_editorial_source": str(item.get("gate") or "UNKNOWN"),
                "slot_state": "FROZEN_REFERENCE_ONLY"
                if reference_only
                else "EDITORIAL_PROPOSAL_ONLY",
                "frozen_ref": reference if reference_only else None,
                "frozen_sha256": item.get("frozen_sha256") if reference_only else None,
                "hook_state": "EXACT_SOURCE_RETRIEVAL_REQUIRED"
                if reference_only
                else "DRAFT_NOT_APPROVED",
                "scheduled": False,
                "published": False,
                "owner_publication_go": False,
            }
        )
    if any(
        (date.fromisoformat(output[i + 1]["date"]) - date.fromisoformat(output[i]["date"])).days
        != 1
        for i in range(29)
    ):
        return packet("BLOCKED", {}, ["calendar_not_contiguous"])
    if incomplete_hook_dates:
        return packet(
            "BLOCKED",
            {"slots": output, "incomplete_hook_dates": incomplete_hook_dates},
            ["calendar_has_non_concrete_hook_placeholders"],
        )
    return packet(
        "DONE_WITH_HOLDS",
        {
            "slots": output,
            "auto_schedule": False,
            "test_mix_is_nonbinding": True,
            "frozen_reference_dates": frozen_reference_holds,
        },
        ["per_asset_rights_audio_ai_and_separate_owner_publish_go_required"]
        + (["frozen_references_are_not_completed_post_copy"] if frozen_reference_holds else []),
    )


HANDLERS = {
    "W1": growth_blueprint,
    "W2": viral_writer,
    "W3": audience_magnet,
    "W4": authority_builder,
    "W5": engagement_loop,
    "W6": emotional_hooks,
    "W7": thirty_day_calendar,
}


class EditorialRunner:
    """Seven individually executable, restartable role handlers; local only."""

    def __init__(self, *, round_id: str, pilot: dict, existing: dict, checkpoint: Path):
        if not re.fullmatch(r"dufynd_editorial_[a-z0-9_]{6,100}", round_id):
            raise WorkerInputError("invalid_round_id")
        if not isinstance(pilot, dict) or not isinstance(existing, dict):
            raise WorkerInputError("invalid_editorial_inputs")
        self.round_id, self.pilot, self.existing = round_id, pilot, existing
        self.checkpoint = checkpoint
        repository = Path(__file__).resolve().parents[1]
        if repository == checkpoint.resolve() or repository in checkpoint.resolve().parents:
            raise WorkerInputError("private_checkpoint_cannot_write_into_public_repo")
        self.input_hash = digest({"round": round_id, "pilot": pilot, "existing": existing})

    def _read(self) -> dict:
        if self.checkpoint.exists():
            state = json.loads(self.checkpoint.read_text(encoding="utf-8"))
            if (
                state.get("schema_version") != SCHEMA_VERSION
                or state.get("round_id") != self.round_id
                or state.get("input_sha256") != self.input_hash
            ):
                raise WorkerInputError("checkpoint_input_fingerprint_mismatch")
            if not isinstance(state.get("role_packets"), dict):
                raise WorkerInputError("malformed_checkpoint_role_packets")
            for field in ("media_created", "published", "scheduled"):
                if state.get(field) is not False:
                    raise WorkerInputError("checkpoint_safety_marker_modified")
            for field in ("model_requests", "external_requests", "spend_eur"):
                if type(state.get(field)) is not int or state[field] != 0:
                    raise WorkerInputError("checkpoint_safety_marker_modified")
            for role, saved in state["role_packets"].items():
                if role not in ROLE_ORDER or not isinstance(saved, dict):
                    raise WorkerInputError("unrecognized_checkpoint_role")
                if "role" not in saved:
                    if saved.get("state") != "BLOCKED":
                        raise WorkerInputError("invalid_dependency_block_state")
                    continue
                dependencies = DEPENDENCIES[role]
                if saved.get("role") != role or saved.get("depends_on") != list(dependencies):
                    raise WorkerInputError("checkpoint_role_contract_mismatch")
                if saved.get("output_sha256") != digest(saved.get("output")):
                    raise WorkerInputError("checkpoint_output_integrity_failed")
                if any(dependency not in state["role_packets"] for dependency in dependencies):
                    raise WorkerInputError("checkpoint_dependency_missing")
                source_hash = digest(
                    {
                        "source": self.pilot.get(role),
                        "upstream": [
                            state["role_packets"][dependency]["output"]
                            for dependency in dependencies
                        ],
                    }
                )
                if saved.get("input_sha256") != source_hash:
                    raise WorkerInputError("checkpoint_input_integrity_failed")
            return state
        return {
            "schema_version": SCHEMA_VERSION,
            "round_id": self.round_id,
            "input_sha256": self.input_hash,
            "role_packets": {},
            "media_created": False,
            "model_requests": 0,
            "external_requests": 0,
            "spend_eur": 0,
            "published": False,
            "scheduled": False,
        }

    def _write(self, state: dict) -> None:
        self.checkpoint.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.checkpoint.with_name(
            self.checkpoint.name + "." + str(os.getpid()) + ".tmp"
        )
        file_descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
                json.dump(state, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.checkpoint)
        finally:
            if temporary.exists():
                temporary.unlink()

    def run(self, role: str | None = None) -> dict:
        if role is not None and role not in ROLE_ORDER:
            raise WorkerInputError("unknown_content_worker_role")
        lock_path = self.checkpoint.with_suffix(self.checkpoint.suffix + ".lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a+b") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            state = self._read()
            for current in ROLE_ORDER if role is None else (role,):
                if current in state["role_packets"]:
                    continue  # Idempotence; never fabricate repeat work.
                prerequisites = DEPENDENCIES[current]
                missing = [
                    dep
                    for dep in prerequisites
                    if state["role_packets"].get(dep, {}).get("state") not in SUCCESS_STATES
                ]
                if missing:
                    if role is not None:
                        raise WorkerInputError("unmet_dependencies:" + ",".join(missing))
                    state["role_packets"][current] = packet(
                        "BLOCKED", {}, ["unmet_dependencies:" + ",".join(missing)]
                    )
                    self._write(state)
                    continue
                section = self.pilot.get(current)
                result = (
                    HANDLERS[current](section, state["role_packets"], self.existing)
                    if isinstance(section, dict)
                    else packet("BLOCKED", {}, ["missing_input_for_role:" + current])
                )
                state["role_packets"][current] = {
                    "role": current,
                    "name": ROLE_NAMES[current],
                    "depends_on": list(prerequisites),
                    "input_sha256": digest(
                        {
                            "source": section,
                            "upstream": [
                                state["role_packets"][dep]["output"] for dep in prerequisites
                            ],
                        }
                    ),
                    "output_sha256": digest(result["output"]),
                    **result,
                }
                self._write(state)
            state["ready_for_editorial_text_review"] = all(
                state["role_packets"].get(key, {}).get("state") in SUCCESS_STATES
                for key in ROLE_ORDER
            )
            state["ready_for_owner_creative_review"] = False
            state["ready_for_publication"] = False
            state["chief_editor_gate"] = "TEXT_ONLY_NO_VISUAL_QA_NO_OWNER_APPROVAL"
            self._write(state)
            return state


def load_private_source(source_key: str) -> dict:
    if source_key != "content.seven_worker_editorial_pilot_20261011_v1":
        raise WorkerInputError("unapproved_private_source_key")
    from scripts.dufynd_jarvis_bridge import DufyndJarvisBridge

    row = DufyndJarvisBridge().load_master_status_entry(source_key)
    value = (row or {}).get("value")
    if not isinstance(value, dict):
        raise WorkerInputError("private_editorial_source_unavailable")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Run bounded zero-cost editorial role validation")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="Private local editorial-pilot JSON")
    source.add_argument(
        "--private-source-key", help="Existing permitted Supabase record (read only)"
    )
    parser.add_argument(
        "--output", type=Path, required=True, help="PRIVATE local checkpoint, never public Git"
    )
    parser.add_argument(
        "--role", choices=ROLE_ORDER, help="Run exactly one worker after prerequisites"
    )
    args = parser.parse_args()
    # Private editorial results must never be written into this public repository.
    if Path(__file__).resolve().parents[1] in args.output.resolve().parents:
        raise WorkerInputError("private_checkpoint_cannot_write_into_public_repo")
    if args.input:
        data = json.loads(args.input.read_text(encoding="utf-8"))
    else:
        data = load_private_source(args.private_source_key)
    if not isinstance(data, dict):
        raise WorkerInputError("editorial_source_is_not_an_object")
    pilot = data.get("pilot", data)
    round_id = str(data.get("round_id") or "")
    existing = data.get("existing", {"reserved": {"2026-10-12": "Torwart"}})
    result = EditorialRunner(
        round_id=round_id, pilot=pilot, existing=existing, checkpoint=args.output
    ).run(args.role)
    print(
        json.dumps(
            {
                "round_id": round_id,
                "role_states": {k: v["state"] for k, v in result["role_packets"].items()},
                "owner_review": result["ready_for_owner_creative_review"],
                "publication": result["ready_for_publication"],
                "provider_calls": result["model_requests"],
                "spend_eur": result["spend_eur"],
                "checkpoint_sha256": digest(result),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
