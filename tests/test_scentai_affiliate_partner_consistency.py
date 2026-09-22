from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

DATA_DIR = Path("examples/retail/data")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_affiliate_programs_match_partner_registry_state() -> None:
    programs = load_json(DATA_DIR / "scentai_affiliate_programs.json")
    partners = load_json(DATA_DIR / "merchant_partners.json")

    partner_by_id = {row["merchant_id"]: row for row in partners["partners"]}

    applications = list(programs.get("applications", []))
    applications.extend(programs.get("other_networks", []))

    tracked = [
        row
        for row in applications
        if row.get("status") in {"applied", "applied_pending", "approved"}
    ]

    assert tracked

    for application in tracked:
        merchant_id = application.get("merchant_id")
        assert merchant_id, f"Affiliate application lacks merchant_id: {application}"
        assert merchant_id in partner_by_id, (
            f"Affiliate application merchant_id {merchant_id!r} "
            "is missing from merchant_partners.json"
        )

        partner = partner_by_id[merchant_id]
        status = application.get("status")

        if status in {"applied", "applied_pending"}:
            assert partner["status"] == "pending_affiliate_link", (
                f"{merchant_id}: applied/pending program must not be active "
                "before approved tracking is configured"
            )
            assert partner.get("affiliate_url") is None, (
                f"{merchant_id}: pending partner must not expose a guessed affiliate URL"
            )
            continue

        assert status == "approved"
        tracking_strategy = str(application.get("tracking_strategy") or "")

        if tracking_strategy == "verified_awin_partner_homepage_link":
            assert partner["status"] == "active", (
                f"{merchant_id}: approved homepage-tracked program should be active"
            )
            affiliate_url = partner.get("affiliate_url")
            assert affiliate_url, f"{merchant_id}: approved homepage partner lacks affiliate_url"
            parsed = urlparse(affiliate_url)
            assert parsed.scheme == "https" and parsed.netloc, (
                f"{merchant_id}: approved homepage partner must use a valid HTTPS affiliate URL"
            )
            assert partner.get("last_verified_at"), (
                f"{merchant_id}: approved homepage partner must record link verification time"
            )
            continue

        assert partner["status"] == "pending_affiliate_link", (
            f"{merchant_id}: approved program without a verified homepage route "
            "must remain gated in the merchant partner registry"
        )
        assert partner.get("affiliate_url") is None, (
            f"{merchant_id}: gated partner must not expose a guessed homepage affiliate URL"
        )
