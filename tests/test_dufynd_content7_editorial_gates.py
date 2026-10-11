"""Regression cases for actual pilot defects, using original synthetic drafts."""

import copy

import pytest
from scripts.dufynd_seven_content_workers import HANDLERS, ROLE_ORDER, digest
from tests.test_dufynd_seven_content_dispatch import editorial_fixture


def packets(source):
    prior = {}
    for role in ROLE_ORDER:
        prior[role] = HANDLERS[role](source[role], prior, {})
    return prior


@pytest.mark.parametrize(
    "text",
    [
        "Preserve frozen original text or draft a distinct hook at preproduction",
        "TBD",
        "TODO",
        "Platzhalter",
        "Hook folgt",
        "Insert hook",
        "",
    ],
)
def test_placeholder_cannot_be_calendar_success(text):
    section = editorial_fixture()["W7"]
    section["calendar"][15]["hook"] = text
    assert HANDLERS["W7"](section, {}, {})["state"] == "BLOCKED"


@pytest.mark.parametrize("field", ["hook", "question"])
def test_exact_crosslink_not_close_text_match(field):
    source = editorial_fixture()
    source["W2"]["ideas"][3][field] += " "
    result = packets(source)["W2"]
    assert result["state"] == "BLOCKED"
    assert result["output"]["broken_crosslink_ids"] == ["idea_3"]


def test_good_crosslinks_and_frozen_duplicate_never_shortlisted():
    source = editorial_fixture()
    prior = packets(source)
    result = HANDLERS["W2"](
        source["W2"], prior, {"frozen_titles": [source["W2"]["ideas"][0]["title"]]}
    )
    assert result["state"] == "DONE_WITH_HOLDS"
    assert "idea_0" not in {v["id"] for v in result["output"]["editorial_shortlist"]}
    assert not any(v["creative_approval"] for v in result["output"]["ideas"])


def test_frozen_reference_is_distinct_from_complete_copy_and_cannot_be_rewritten():
    source = editorial_fixture()["W7"]
    fingerprint = digest({"title": "Immutable original synthetic final"})
    source["calendar"][0].update(
        hook="", reference_only=True, frozen_ref="content.test.final", frozen_sha256=fingerprint
    )
    existing = {"frozen_refs": {"content.test.final": {"record_sha256": fingerprint}}}
    result = HANDLERS["W7"](source, {}, existing)
    assert result["state"] == "DONE_WITH_HOLDS"
    assert result["output"]["slots"][0]["hook_state"] == "EXACT_SOURCE_RETRIEVAL_REQUIRED"
    assert "frozen_references_are_not_completed_post_copy" in result["holds"]
    changed = copy.deepcopy(source)
    changed["calendar"][0]["hook"] = "A new unauthorized hook"
    assert HANDLERS["W7"](changed, {}, existing)["state"] == "BLOCKED"
    changed["calendar"][0]["hook"] = ""
    changed["calendar"][0]["frozen_sha256"] = "0" * 64
    assert HANDLERS["W7"](changed, {}, existing)["state"] == "BLOCKED"


def test_blocked_pattern_does_not_stop_independent_authority_role():
    source = editorial_fixture()
    source["W3"]["patterns"] = []
    result = packets(source)
    assert result["W3"]["state"] == "BLOCKED"
    assert result["W4"]["state"] == "DONE_WITH_HOLDS"
