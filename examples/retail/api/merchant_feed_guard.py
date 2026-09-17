from __future__ import annotations


def find_duplicate_offer_ids(
    rows: list[dict],
) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()

    for row in rows:
        value = row.get("offer_id")

        if value is None:
            continue

        offer_id = str(value).strip()

        if offer_id in seen:
            duplicates.add(offer_id)
        else:
            seen.add(offer_id)

    return sorted(duplicates)
