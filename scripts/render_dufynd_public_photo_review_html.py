"""Human-only visual contact sheet for current official Awin public-photo leads.

Reads the sanitized, review-only JSON packet. No feed credentials, offers, prices,
registration writes, public deployments, or automated photo approvals.
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

if __package__:
    from .report_dufynd_public_photo_feed_leads import safe_feed_image
else:
    from report_dufynd_public_photo_feed_leads import safe_feed_image

PRIORITY_IDS = (
    "SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100",
    "SC-RABANNE-1-MILLION-EDT-100",
    "SC-XERJOFF-NAXOS-100",
    "SC-PDM-LAYTON-125",
    "SC-LV-IMAGINATION-100",
)
ALLOWED_MATCHES = {
    "mapped_sku_needs_feed_variant_review",
    "name_lead_manual_sku_mapping_required",
}
MAX_ITEMS = 250
MAX_CANDIDATES = 3


def _text(value: object) -> str:
    return html.escape(str(value or "")[:250], quote=True)


def _sort_key(item: dict) -> tuple[int, int, str]:
    product_id = str(item.get("product_id") or "")
    try:
        priority = PRIORITY_IDS.index(product_id)
    except ValueError:
        priority = len(PRIORITY_IDS)
    return (0 if item.get("candidates") else 1, priority, product_id)


def render_review_html(packet: dict) -> str:
    if (
        packet.get("schema") != "dufynd_licensed_feed_photo_review_v1"
        or packet.get("status") != "REVIEW_ONLY_NOT_LIVE"
        or packet.get("automated_registration_allowed") is not False
        or packet.get("product_offer_activation_allowed") is not False
        or packet.get("approved_new_images") != 0
    ):
        raise ValueError("review_only_provenance_required")

    source = packet.get("feed_provenance") or {}
    if (
        str(source.get("advertiser_id")) != "31081"
        or str(source.get("feed_id")) != "91379"
        or source.get("source") != "awin_product_feed_list"
        or not source.get("checked_at")
        or packet.get("source_rights_basis_id")
        != "awin_top_parfuemerie_feed_materials_20260928"
    ):
        raise ValueError("official_feed_rights_provenance_required")

    items = packet.get("items")
    if not isinstance(items, list) or not 0 < len(items) <= MAX_ITEMS:
        raise ValueError("bounded_public_photo_gap_required")
    if packet.get("products_reviewed") != len(items):
        raise ValueError("review_count_mismatch")

    seen: set[str] = set()
    cards: list[str] = []
    holds: list[str] = []
    found = 0
    for item in sorted(items, key=_sort_key):
        pid = str(item.get("product_id") or "")
        if not pid or pid in seen:
            raise ValueError("missing_or_duplicate_product_id")
        seen.add(pid)
        raw_candidates = item.get("candidates")
        if not isinstance(raw_candidates, list) or len(raw_candidates) > MAX_CANDIDATES:
            raise ValueError("unbounded_photo_leads")
        name = f"{_text(item.get('brand'))} · {_text(item.get('name'))}"
        variant = f"{_text(item.get('concentration'))} · {_text(item.get('volume_ml'))} ml"
        if not raw_candidates:
            holds.append(f"<li><strong>{name}</strong> <small>{_text(pid)}</small></li>")
            continue

        blocks: list[str] = []
        for candidate in raw_candidates:
            match = candidate.get("match_type")
            image = safe_feed_image(candidate.get("feed_image_url"))
            if (
                match not in ALLOWED_MATCHES
                or image is None
                or candidate.get("status") != "HUMAN_SOURCE_VARIANT_IMAGE_REVIEW_REQUIRED"
                or candidate.get("registered") is not False
                or candidate.get("published") is not False
            ):
                raise ValueError("unapproved_or_unsafe_image_candidate")
            label = (
                "Bekannte Händler-SKU · Variante manuell abgleichen"
                if match == "mapped_sku_needs_feed_variant_review"
                else "Namensfund · SKU und Variante unabhängig prüfen"
            )
            size = (
                "Größe im Feedtitel vorhanden"
                if candidate.get("feed_explicit_size_match") is True
                else "Größe im Feedtitel NICHT bestätigt"
            )
            safe_url = html.escape(image, quote=True)
            blocks.append(
                f'<div class="option"><div class="image"><img loading="lazy" '
                f'referrerpolicy="no-referrer" src="{safe_url}" '
                f'alt="Ungeprüfter Händlerfoto-Kandidat für {name}"></div>'
                f'<div class="meta"><p><strong>{_text(label)}</strong></p>'
                f'<p>{_text(size)} · SKU {_text(candidate.get("merchant_product_id"))}</p>'
                f'<p>{_text(candidate.get("merchant_product_name"))}</p>'
                f'<p><a href="{safe_url}" rel="noopener noreferrer" target="_blank">'
                f'Originale Händlerbilddatei ansehen</a></p>'
                f'<p class="hold">HOLD: Keine Bild-, Varianten- oder Publikationsfreigabe</p>'
                f'</div></div>'
            )
            found += 1
        cards.append(
            f'<article class="card"><h2>{name}</h2><p>{variant}</p>'
            f'<code>{_text(pid)}</code>{"".join(blocks)}</article>'
        )

    if found != packet.get("total_review_candidates"):
        raise ValueError("candidate_count_mismatch")
    if len(cards) != packet.get("products_with_leads"):
        raise ValueError("product_lead_count_mismatch")

    hold_html = "<ul>" + "".join(holds) + "</ul>" if holds else "<p>Keine.</p>"
    card_html = "".join(cards) or "<p>Keine Bildkandidaten im aktuellen Feed gefunden.</p>"
    checked = _text(source.get("checked_at"))
    imported = _text(source.get("last_imported") or "nicht verfügbar")
    return f"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy"
 content="default-src 'none'; img-src https://topparfuemerie.de https://www.topparfuemerie.de; style-src 'unsafe-inline';">
<title>DUFYND · Originalfoto-Prüfung (nicht freigegeben)</title>
<style>
:root {{font: 15px/1.5 system-ui,sans-serif; color:#24282b; background:#f4f2ee}}
body {{max-width:1160px; margin:auto; padding:24px}}
header {{padding:20px 0 32px}}
h1 {{font-size:clamp(26px,4vw,40px); letter-spacing:-.04em}}
h2 {{font-size:21px; margin:0}}
small,code {{overflow-wrap:anywhere; color:#62676b}}
.note {{background:#fff; border-left:4px solid #ad6851; padding:14px 18px}}
.cards {{display:grid; gap:16px}}
.card {{background:#fff; padding:24px; border-radius:16px; border:1px solid #e3ded6}}
.option {{display:grid; grid-template-columns:minmax(160px,270px) 1fr; gap:20px; padding:18px 0; border-top:1px solid #e6e2db; margin-top:12px}}
.image {{background:#efefeb; min-height:210px; display:grid; place-items:center; border-radius:10px}}
.image img {{width:100%; height:250px; object-fit:contain}}
.meta p {{margin:8px 0}}
.hold {{font-weight:700; color:#903a2f}}
details {{margin-top:28px; background:#fff; padding:18px; border-radius:12px}}
li {{margin:6px 0}}
a {{color:#244a5c}}
@media(max-width:620px) {{.option {{grid-template-columns:1fr}} .card {{padding:16px}}}}
</style>
</head>
<body>
<header>
<p>DUFYND / SOURCING / VERTRAULICHE PRÜFVORSCHAU</p>
<h1>Echte Originalfotos – Kandidatenprüfung</h1>
<p class="note"><strong>Nicht freigegeben.</strong> Die Bilder sind ausschließlich
aktuelle Awin-Feed-Kandidaten. Händler-SKU, Originalflakon, exakte Variante,
Nutzungsumfang und Bildbytes müssen separat geprüft werden. Keine automatische
Produktbildübernahme oder Angebotsaktivierung.</p>
<p>Feed 91379 · Advertiser 31081 · geprüft: {checked} · Feedimport: {imported}</p>
<p>{len(items)} offene Profile · {len(cards)} Profile mit Kandidaten · {found} Bildfunde
 · <strong>0 neue Bildfreigaben</strong></p>
</header>
<main><section class="cards">{card_html}</section>
<details><summary>{len(holds)} Profile ohne geeigneten Bildfund anzeigen</summary>
{hold_html}</details></main>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.candidates.stat().st_size > 4_000_000:
            raise ValueError("oversized_review_packet")
        packet = json.loads(args.candidates.read_text(encoding="utf-8"))
        document = render_review_html(packet)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(document, encoding="utf-8")
    except (ValueError, OSError, json.JSONDecodeError):
        parser.exit(2, "photo_review_html_failed_closed\n")
    print("DUFYND public photo contact sheet: review-only, zero approvals")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
