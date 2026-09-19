from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path("examples/retail/data")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_applied_affiliate_programs_have_partner_registry_entries() -> None:
    programs = load_json(DATA_DIR / "scentai_affiliate_programs.json")
    partners = load_json(DATA_DIR / "merchant_partners.json")

    partner_by_id = {row["merchant_id"]: row for row in partners["partners"]}

    applications = list(programs.get("applications", []))
    applications.extend(programs.get("other_networks", []))

    tracked = [row for row in applications if row.get("status") in {"applied", "applied_pending"}]

    assert tracked

    for application in tracked:
        merchant_id = application.get("merchant_id")
        assert merchant_id, f"Affiliate application lacks merchant_id: {application}"
        assert merchant_id in partner_by_id, (
            f"Affiliate application merchant_id {merchant_id!r} "
            "is missing from merchant_partners.json"
        )

        partner = partner_by_id[merchant_id]
        assert partner["status"] == "pending_affiliate_link", (
            f"{merchant_id}: applied/pending program must not be active "
            "before approved tracking is configured"
        )
        assert partner.get("affiliate_url") is None, (
            f"{merchant_id}: pending partner must not expose a guessed affiliate URL"
        )
