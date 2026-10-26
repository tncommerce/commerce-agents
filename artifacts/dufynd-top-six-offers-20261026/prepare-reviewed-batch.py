"""Dry-run six proposed exact routes in memory; never applies live configuration."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

PACKET = Path(__file__).resolve().parent
ROOT = PACKET.parents[1]
sys.path.insert(0, str(ROOT))

from scripts.prepare_dufynd_runtime_offer_batch import batch_digest, prepare_batch  # noqa: E402


def read(path: Path) -> dict:
    return json.loads(path.read_text())


evidence = read(PACKET / "batch-input.json")
prepared = prepare_batch(
    read(PACKET / "proposed-offers.json")["offers"],
    evidence,
    now=datetime.now(UTC),
    partners_payload={"partners": [read(PACKET / "proposed-partner.json")]},
    mappings_payload=read(PACKET / "proposed-mappings.json"),
    catalog_payload=read(ROOT / "examples/retail/data/catalog.json"),
)
print(
    json.dumps(
        {
            "mode": "DRY_RUN_PROPOSED_CONFIGURATION_NOT_LIVE",
            "checked_at": datetime.now(UTC).isoformat(),
            "batch_id": evidence["batch_id"],
            "batch_sha256": batch_digest(prepared, batch_id=evidence["batch_id"]),
            "offer_count": len(prepared),
            "production_changed": False,
            "offers": prepared,
        },
        ensure_ascii=False,
        indent=2,
    )
)
