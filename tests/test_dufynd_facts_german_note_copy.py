"""41-source German presentation guard; no synthetic perfume facts or approvals."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.dufynd_localize_note_descriptions import (
    DISCLAIMER,
    labels,
    localized_description,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "examples/retail/data"
GENERATED = ROOT / "examples/retail/storefront-web/lib/generated/released-profiles.json"


def test_all_41_note_lists_have_german_display_labels() -> None:
    translations = labels()
    waves = [
        json.loads((DATA / f"dufynd_facts_wave_0{i}_review.json").read_text(encoding="utf-8"))
        for i in (1, 2)
    ]
    assert [len(p["profiles"]) for p in waves] == [20, 21]
    assert all(p["public_release_authorized"] is False for p in waves)
    for packet in waves:
        for row in packet["profiles"]:
            assert row["editorial_description_de"] == localized_description(row, translations)
            assert row["editorial_description_de"].startswith(row["summary_de"] + " ")
            is_key_only = bool(row["notes"].get("key"))
            assert (DISCLAIMER in row["editorial_description_de"]) == is_key_only
            assert not any(
                forbidden in row["editorial_description_de"].lower()
                for forbidden in ("affiliate", "preis: ", "jetzt kaufen")
            )


def test_released_20_only_and_no_second_wave_activation() -> None:
    first = json.loads((DATA / "dufynd_facts_wave_01_review.json").read_text(encoding="utf-8"))
    second = json.loads((DATA / "dufynd_facts_wave_02_review.json").read_text(encoding="utf-8"))
    public = json.loads(GENERATED.read_text(encoding="utf-8"))["profiles"]
    first_by_id = {row["product_id"]: row for row in first["profiles"]}
    assert len(public) == 20
    assert {row["product_id"] for row in public} == set(first_by_id)
    assert not {row["product_id"] for row in second["profiles"]}.intersection(first_by_id)
    for row in public:
        review = first_by_id[row["product_id"]]
        assert row["editorial_description_de"] == review["editorial_description_de"]
        assert row["notes"] == review["notes"]
        assert row["seo"] == review["seo"]
        assert row["indexing_approved"] is True
        assert not any(
            key in row
            for key in ("price", "image_url", "affiliate_url", "merchant_id", "in_stock")
        )


def test_rebuild_idempotent_and_does_not_write_during_check() -> None:
    script = ROOT / "scripts/dufynd_localize_note_descriptions.py"
    before = GENERATED.read_bytes()
    completed = subprocess.run(
        [sys.executable, str(script)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert GENERATED.read_bytes() == before
