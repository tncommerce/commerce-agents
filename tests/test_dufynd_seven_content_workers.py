"""Offline acceptance for the seven distinct fail-closed content workers.

All fixtures are synthetic. Real unpublished Owner content remains only in private
Supabase/Library; nothing is copied to public GitHub test data.
"""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from scripts.dufynd_seven_content_workers import (
    DEPENDENCIES,
    ROLE_ORDER,
    EditorialRunner,
    WorkerInputError,
    digest,
    valid_source_url,
)


def editorial_fixture() -> dict:
    hooks = [f"Ein anderer Duftmoment Nummer {i}: Das kann doch nicht sein!" for i in range(20)]
    questions = [
        f"An welchem echten Duftmoment Nummer {i} erinnerst du dich persönlich?" for i in range(10)
    ]
    start = date(2026, 10, 12)
    days = [
        {
            "date": (start + timedelta(days=i)).isoformat(),
            "idea": "Torwart Original Meme" if i == 0 else f"Distinct editorial day {i}",
            "hook": "Unverändertes Torwart Motiv"
            if i == 0
            else f"Neue Idee {i} mit konkretem Anlass",
            "format": "meme" if i % 3 == 0 else "carousel",
            "gate": "CREATIVE_FROZEN_CONDITIONAL_PUBLISH_GO" if i == 0 else "IDEA_ONLY",
            "published": True,  # Hostile/source metadata must never grant publication.
        }
        for i in range(30)
    ]
    return {
        "W1": {
            "audience": "non-collectors and curious fragrance enthusiasts",
            "voice": "warm and humorous, without false product effects",
            "channels": "TikTok photo; Instagram reels; real YouTube video",
            "goals": ["shares", "comments", "verified site visits"],
            "observations": "This is a historical snapshot, not a causal claim.",
            "cadence_test_mix": {"meme": 12, "carousel": 9, "reel": 6, "slideshow": 3},
        },
        "W3": {
            "patterns": [
                {
                    "url": "https://www.reddit.com/r/fragrance/comments/valid_sample_a/",
                    "date": "2026-10-05",
                    "mechanic": "Visually obvious social anecdote and a concrete reader question.",
                },
                {
                    "url": "https://www.reddit.com/r/fragrance/comments/valid_sample_b/",
                    "date": "2026-10-06",
                    "mechanic": "Everyday fragrance-related disagreement without product claims.",
                },
            ]
        },
        "W4": {
            "insights": [
                {
                    "id": f"fake_insight_{i}",
                    "theme": f"Independent educational topic {i}",
                    "claim": f"An editorial draft insight requiring a source check {i}",
                    "source_url": f"https://example.org/scent/{i}",
                    "source_verified": True,  # Cannot prove verification by claiming it!
                }
                for i in range(5)
            ]
        },
        "W5": {"questions": questions},
        "W6": {"hooks": hooks},
        "W2": {
            "ideas": [
                {
                    "id": f"draft_concept_{i}",
                    "title": "Already published scent"
                    if i == 2
                    else f"Distinct theme and story {i}",
                    "hook": hooks[i],
                    "question": questions[i],
                    "format": "meme",
                    "concept": f"A specific original everyday scene {i}",
                    "overlap": "distinct",
                    "visual_QA": "APPROVED",
                    "publish_go": True,
                    "owner_creative_go": True,
                }
                for i in range(10)
            ]
        },
        "W7": {"calendar": days},
    }


class SevenWorkerRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.file = Path(self.temp.name) / "private" / "checkpoint.json"
        self.pilot = editorial_fixture()
        self.existing = {
            "reserved": {"2026-10-12": "Torwart"},
            "published_titles": ["Already published scent"],
            "frozen_titles": ["Frozen owner visual"],
        }

    def runner(self, pilot=None, existing=None):
        return EditorialRunner(
            round_id="dufynd_editorial_seven_workers_integration_v1",
            pilot=pilot if pilot is not None else self.pilot,
            existing=existing if existing is not None else self.existing,
            checkpoint=self.file,
        )

    def test_exactly_seven_distinct_handlers_and_dag(self):
        self.assertEqual(len(ROLE_ORDER), 7)
        self.assertEqual(set(DEPENDENCIES), set(ROLE_ORDER))
        for role in ROLE_ORDER:
            for dependency in DEPENDENCIES[role]:
                self.assertLess(ROLE_ORDER.index(dependency), ROLE_ORDER.index(role))
        self.assertEqual(DEPENDENCIES["W3"], ("W1",))
        self.assertEqual(DEPENDENCIES["W4"], ("W1",))

    def test_full_true_offline_assembly_no_creative_or_public_approval(self):
        state = self.runner().run()
        self.assertEqual(set(state["role_packets"]), set(ROLE_ORDER))
        self.assertTrue(state["ready_for_owner_creative_review"])
        self.assertFalse(state["ready_for_publication"])
        self.assertEqual(state["model_requests"], 0)
        self.assertEqual(state["external_requests"], 0)
        self.assertEqual(state["spend_eur"], 0)
        self.assertFalse(state["media_created"])
        self.assertFalse(state["published"])
        self.assertFalse(state["scheduled"])
        self.assertEqual(
            len(state["role_packets"]["W1"]["output"]["test_mix_not_a_posting_quota"]), 4
        )
        self.assertEqual(len(state["role_packets"]["W2"]["output"]["ideas"]), 10)
        self.assertEqual(len(state["role_packets"]["W3"]["output"]["reference_mechanics"]), 2)
        self.assertEqual(len(state["role_packets"]["W4"]["output"]["fact_candidates"]), 5)
        self.assertEqual(len(state["role_packets"]["W5"]["output"]["questions"]), 10)
        self.assertEqual(len(state["role_packets"]["W6"]["output"]["hooks"]), 20)
        self.assertEqual(len(state["role_packets"]["W7"]["output"]["slots"]), 30)
        self.assertTrue(
            all(
                not x["facts_cleared_for_publication"]
                for x in state["role_packets"]["W4"]["output"]["fact_candidates"]
            )
        )
        self.assertTrue(
            all(
                x["creative_approval"] is False and x["publication_approval"] is False
                for x in state["role_packets"]["W2"]["output"]["ideas"]
            )
        )
        self.assertTrue(
            all(
                x["slot_state"] == "EDITORIAL_PROPOSAL_ONLY" and not x["published"]
                for x in state["role_packets"]["W7"]["output"]["slots"]
            )
        )
        self.assertEqual(
            state["role_packets"]["W2"]["output"]["ideas"][2]["review_holds"],
            ["existing_frozen_or_published_creative"],
        )
        self.assertTrue(self.file.is_file())
        self.assertEqual(json.loads(self.file.read_text()), state)

    def test_each_independent_worker_needs_real_previous_packet(self):
        runner = self.runner()
        with self.assertRaisesRegex(WorkerInputError, "unmet_dependencies"):
            runner.run("W2")
        for role in ROLE_ORDER:
            runner.run(role)
        done = runner.run()
        self.assertTrue(done["ready_for_owner_creative_review"])
        before = self.file.read_bytes()
        runner.run()
        self.assertEqual(before, self.file.read_bytes())

    def test_w3_and_w4_are_independent_but_w5_depends_on_w3(self):
        runner = self.runner()
        runner.run("W1")
        runner.run("W4")
        with self.assertRaisesRegex(WorkerInputError, "unmet_dependencies"):
            runner.run("W5")
        runner.run("W3")
        state = runner.run("W5")
        self.assertEqual(state["role_packets"]["W5"]["state"], "DONE")

    def test_source_recheck_never_silently_passes(self):
        state = self.runner().run()
        self.assertEqual(state["role_packets"]["W3"]["state"], "DONE_WITH_HOLDS")
        self.assertEqual(state["role_packets"]["W4"]["state"], "DONE_WITH_HOLDS")
        self.assertEqual(
            state["role_packets"]["W3"]["output"]["reference_mechanics"][0][
                "fresh_page_verification"
            ],
            "NOT_PERFORMED_BY_OFFLINE_WORKER",
        )

    def test_stale_restart_refuses_changed_private_inputs(self):
        self.runner().run("W1")
        changed = copy.deepcopy(self.pilot)
        changed["W1"]["voice"] = "changed midflight"
        with self.assertRaisesRegex(WorkerInputError, "fingerprint_mismatch"):
            self.runner(pilot=changed).run()

    def test_missing_questions_stop_later_workers_but_not_independent_sources(self):
        changed = copy.deepcopy(self.pilot)
        changed["W5"]["questions"] = changed["W5"]["questions"][:9]
        state = self.runner(pilot=changed).run()
        self.assertEqual(state["role_packets"]["W4"]["state"], "DONE_WITH_HOLDS")
        self.assertEqual(state["role_packets"]["W5"]["state"], "BLOCKED")
        self.assertEqual(state["role_packets"]["W6"]["state"], "BLOCKED")
        self.assertEqual(state["role_packets"]["W2"]["state"], "BLOCKED")
        self.assertEqual(state["role_packets"]["W7"]["state"], "BLOCKED")
        self.assertFalse(state["ready_for_owner_creative_review"])

    def test_duplicate_reserved_and_noncontiguous_calendar_fail_closed(self):
        for corruption in ("wrong_reserved", "duplicate", "noncontiguous"):
            with self.subTest(corruption=corruption):
                tmp = Path(self.temp.name) / (corruption + ".json")
                changed = copy.deepcopy(self.pilot)
                if corruption == "wrong_reserved":
                    changed["W7"]["calendar"][0]["idea"] = "Unapproved alternate"
                elif corruption == "duplicate":
                    changed["W7"]["calendar"][5]["date"] = changed["W7"]["calendar"][4]["date"]
                else:
                    changed["W7"]["calendar"][-1]["date"] = "2026-11-20"
                state = EditorialRunner(
                    round_id="dufynd_editorial_seven_workers_calendar_v1",
                    pilot=changed,
                    existing=self.existing,
                    checkpoint=tmp,
                ).run()
                self.assertEqual(state["role_packets"]["W7"]["state"], "BLOCKED")
                self.assertFalse(state["ready_for_owner_creative_review"])

    def test_calendar_placeholder_hooks_are_not_pretended_complete(self):
        changed = copy.deepcopy(self.pilot)
        changed["W7"]["calendar"][1]["hook"] = (
            "Preserve frozen original text or draft a distinct hook at preproduction"
        )
        state = self.runner(pilot=changed).run()
        self.assertEqual(state["role_packets"]["W7"]["state"], "BLOCKED")
        self.assertFalse(state["ready_for_owner_creative_review"])
        self.assertEqual(
            state["role_packets"]["W7"]["output"]["incomplete_hook_dates"],
            ["2026-10-13"],
        )

    def test_insecure_or_undated_sources_do_not_become_verified(self):
        self.assertFalse(valid_source_url("http://example.org"))
        self.assertFalse(valid_source_url("https://user:password@example.org/secret"))
        changed = copy.deepcopy(self.pilot)
        changed["W3"]["patterns"][0]["url"] = "http://example.org/not-https"
        changed["W3"]["patterns"][1]["date"] = "not-a-date"
        state = self.runner(pilot=changed).run()
        self.assertEqual(state["role_packets"]["W3"]["state"], "BLOCKED")
        self.assertEqual(state["role_packets"]["W4"]["state"], "DONE_WITH_HOLDS")
        self.assertEqual(state["role_packets"]["W5"]["state"], "BLOCKED")

    def test_deterministic_source_bound_hashes_and_no_provider(self):
        one = self.runner().run()
        other_file = Path(self.temp.name) / "elsewhere.json"
        two = EditorialRunner(
            round_id="dufynd_editorial_seven_workers_integration_v1",
            pilot=self.pilot,
            existing=self.existing,
            checkpoint=other_file,
        ).run()
        self.assertEqual(digest(one), digest(two))
        self.assertEqual(one["input_sha256"], two["input_sha256"])
        self.assertEqual(
            [one["role_packets"][r]["output_sha256"] for r in ROLE_ORDER],
            [two["role_packets"][r]["output_sha256"] for r in ROLE_ORDER],
        )


if __name__ == "__main__":
    unittest.main()
