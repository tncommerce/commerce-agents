"""The authorized facts-only first wave must retain original, real QA evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

DATA = Path("examples/retail/data")
WEB = Path("examples/retail/storefront-web")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def test_exact_20_owner_approvals_bound_to_responsive_browser_qa() -> None:
    source = load(DATA / "dufynd_facts_wave_01_review.json")["profiles"]
    approval = load(DATA / "dufynd_release_authorizations.json")
    qa = load(DATA / "dufynd_release_qa.json")["profiles"]
    by_id = {row["product_id"]: row for row in approval["approvals"]}
    qa_by_id = {row["product_id"]: row for row in qa}
    assert len(source) == len(by_id) == 20
    assert set(by_id) == {row["product_id"] for row in source}
    assert len(qa) == len(qa_by_id) == 41
    assert approval["product_holds"]
    for row in source:
        owner = by_id[row["product_id"]]
        browser = qa_by_id[row["product_id"]]
        assert browser["passed"] is True
        assert browser["widths"] == [320, 390, 768, 1440]
        assert browser["evidence_sha256"] == row["evidence_sha256"]
        assert owner["qa_sha256"] == sha(browser)
        assert owner["evidence_sha256"] == browser["evidence_sha256"]
        assert owner["render_sha256"] == browser["render_sha256"]
        assert owner["publication_approved"] is True
        assert owner["variant_approved"] is True
        assert owner["illustration_approved"] is True
        assert owner["indexing_approved"] is True
        assert owner["approval_reference"] == "DUFYND_CHAT_OWNER_GO_WELLE_1_20261031"


def test_new_20_are_only_editorial_and_remaining_21_stay_held() -> None:
    published = load(WEB / "lib/generated/released-profiles.json")["profiles"]
    second = load(DATA / "dufynd_facts_wave_02_review.json")["profiles"]
    assert len(published) == 20
    assert len(second) == 21
    assert {p["product_id"] for p in published}.isdisjoint({p["product_id"] for p in second})
    for p in published:
        assert p["indexing_approved"] is True
        assert not {"price", "affiliate_url", "merchant_id", "image_url"} & set(p)
