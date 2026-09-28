from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from urllib.parse import urlparse

EXPECTED_ADVERTISER_ID = "31081"
EXPECTED_FEED_ID = "91379"
EXPECTED_RIGHTS_STATUS = "verified_for_publisher_service"
EXPECTED_REVIEW_STATUS = "pending_review"
EXPECTED_DATA_SOURCE = "approved-affiliate-feed"
EXPECTED_APPROVAL_CLASS = "approval_required"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _norm(value: object) -> str:
    return str(value or "").strip()


def _safe_https_url(value: object) -> str:
    url = _norm(value)
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError("candidate_image_url_must_be_public_https")
    return url


def validate_packet(payload: dict) -> list[dict]:
    if _norm(payload.get("status")) != "review_only_not_live":
        raise ValueError("candidate_payload_not_review_only")
    if payload.get("automatic_approval_allowed") is not False:
        raise ValueError("candidate_payload_must_disable_automatic_approval")
    if _norm(payload.get("approval_action_class")) != EXPECTED_APPROVAL_CLASS:
        raise ValueError("candidate_payload_approval_class_invalid")

    provenance = payload.get("feed_provenance") or {}
    if (
        _norm(provenance.get("advertiser_id")) != EXPECTED_ADVERTISER_ID
        or _norm(provenance.get("feed_id")) != EXPECTED_FEED_ID
        or provenance.get("joined") is not True
        or provenance.get("downloaded") is not True
    ):
        raise ValueError("candidate_payload_feed_provenance_invalid")

    checked_at = _norm(provenance.get("checked_at"))
    if not checked_at:
        raise ValueError("candidate_payload_feed_checked_at_missing")

    rows: list[dict] = []
    for candidate in payload.get("candidates", []):
        product_id = _norm(candidate.get("product_id"))
        if not product_id:
            raise ValueError("candidate_product_id_missing")
        if _norm(candidate.get("review_status")) != EXPECTED_REVIEW_STATUS:
            raise ValueError(f"candidate_not_pending_review:{product_id}")
        if candidate.get("exact_variant_verified") is not True:
            raise ValueError(f"candidate_exact_variant_not_verified:{product_id}")
        if _norm(candidate.get("data_source")) != EXPECTED_DATA_SOURCE:
            raise ValueError(f"candidate_data_source_invalid:{product_id}")
        if _norm(candidate.get("proposed_image_status")) != "approved_feed_image":
            raise ValueError(f"candidate_proposed_image_status_invalid:{product_id}")
        if _norm(candidate.get("rights_status")) != EXPECTED_RIGHTS_STATUS:
            raise ValueError(f"candidate_rights_not_verified:{product_id}")
        if _norm(candidate.get("advertiser_id")) != EXPECTED_ADVERTISER_ID:
            raise ValueError(f"candidate_advertiser_mismatch:{product_id}")
        if _norm(candidate.get("feed_id")) != EXPECTED_FEED_ID:
            raise ValueError(f"candidate_feed_mismatch:{product_id}")
        if _norm(candidate.get("feed_checked_at")) != checked_at:
            raise ValueError(f"candidate_feed_checked_at_mismatch:{product_id}")
        if _norm(candidate.get("approval_action_class")) != EXPECTED_APPROVAL_CLASS:
            raise ValueError(f"candidate_approval_class_invalid:{product_id}")

        rights_basis_id = _norm(candidate.get("rights_basis_id"))
        merchant_product_id = _norm(candidate.get("merchant_product_id"))
        if not rights_basis_id or not merchant_product_id:
            raise ValueError(f"candidate_review_metadata_incomplete:{product_id}")

        row = dict(candidate)
        row["image_url"] = _safe_https_url(candidate.get("image_url"))
        rows.append(row)

    rows.sort(key=lambda item: _norm(item.get("product_id")))
    return rows


def render_html(payload: dict) -> str:
    rows = validate_packet(payload)
    provenance = payload["feed_provenance"]

    cards = []
    for row in rows:
        product_id = html.escape(_norm(row.get("product_id")))
        brand = html.escape(_norm(row.get("brand")))
        name = html.escape(_norm(row.get("name")))
        concentration = html.escape(_norm(row.get("concentration")))
        volume_ml = html.escape(_norm(row.get("volume_ml")))
        merchant_product_id = html.escape(_norm(row.get("merchant_product_id")))
        gtin = html.escape(_norm(row.get("gtin")) or "not supplied")
        offer_id = html.escape(_norm(row.get("offer_id")))
        image_url = html.escape(_norm(row.get("image_url")), quote=True)
        rights_basis_id = html.escape(_norm(row.get("rights_basis_id")))
        last_updated_at = html.escape(_norm(row.get("last_updated_at")) or "not supplied")

        cards.append(
            f"""
            <article class="candidate">
              <div class="image-wrap">
                <img src="{image_url}" alt="{brand} {name} {concentration} {volume_ml} ml"
                     loading="lazy" referrerpolicy="no-referrer">
              </div>
              <div class="details">
                <h2>{brand} {name}</h2>
                <p class="variant">{concentration} · {volume_ml} ml</p>
                <dl>
                  <dt>DUFYND product ID</dt><dd><code>{product_id}</code></dd>
                  <dt>Merchant product ID</dt><dd><code>{merchant_product_id}</code></dd>
                  <dt>GTIN / EAN</dt><dd><code>{gtin}</code></dd>
                  <dt>Awin offer ID</dt><dd><code>{offer_id or "not supplied"}</code></dd>
                  <dt>Feed row updated</dt><dd>{last_updated_at}</dd>
                  <dt>Rights basis</dt><dd><code>{rights_basis_id}</code></dd>
                  <dt>Review status</dt><dd><strong>pending_review</strong></dd>
                </dl>
                <p><a href="{image_url}" rel="noreferrer noopener" target="_blank">Open exact feed image</a></p>
                <p class="warning">Human visual approval required. This candidate is not approved and is not live.</p>
              </div>
            </article>
            """
        )

    body = "\n".join(cards)
    if not body:
        body = (
            '<section class="empty"><h2>No pending candidates</h2>'
            "<p>The current exact feed produced no Release 01 image candidates requiring review.</p></section>"
        )

    advertiser = html.escape(_norm(provenance.get("advertiser_id")))
    feed_id = html.escape(_norm(provenance.get("feed_id")))
    checked_at = html.escape(_norm(provenance.get("checked_at")))
    last_imported = html.escape(_norm(provenance.get("last_imported")) or "not supplied")

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="Content-Security-Policy"
        content="default-src 'none'; img-src https: data:; style-src 'unsafe-inline';">
  <title>DUFYND Release 01 · Awin image review</title>
  <style>
    :root {{ color-scheme: light dark; font-family: Inter, system-ui, sans-serif; }}
    body {{ max-width: 1100px; margin: 0 auto; padding: 24px; line-height: 1.5; }}
    header {{ margin-bottom: 28px; }}
    .meta {{ display: grid; grid-template-columns: max-content 1fr; gap: 4px 14px; }}
    .candidate {{ display: grid; grid-template-columns: minmax(220px, 360px) 1fr; gap: 28px;
                  padding: 24px 0; border-top: 1px solid currentColor; }}
    .image-wrap {{ min-height: 300px; display: grid; place-items: center; background: rgba(127,127,127,.08); }}
    img {{ display: block; max-width: 100%; max-height: 520px; object-fit: contain; }}
    dl {{ display: grid; grid-template-columns: max-content 1fr; gap: 6px 14px; }}
    dt {{ font-weight: 700; }}
    dd {{ margin: 0; overflow-wrap: anywhere; }}
    code {{ overflow-wrap: anywhere; }}
    .variant {{ font-size: 1.1rem; }}
    .warning {{ font-weight: 700; border-left: 4px solid currentColor; padding-left: 12px; }}
    @media (max-width: 720px) {{
      .candidate {{ grid-template-columns: 1fr; }}
      dl, .meta {{ grid-template-columns: 1fr; gap: 0; }}
      dt {{ margin-top: 8px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>DUFYND Release 01 · current Awin feed image review</h1>
    <p><strong>Review-only artifact.</strong> Nothing in this file grants final image approval,
       writes to the catalog, activates an offer, or deploys anything.</p>
    <div class="meta">
      <strong>Advertiser</strong><span>{advertiser}</span>
      <strong>Feed</strong><span>{feed_id}</span>
      <strong>Current-feed check</strong><span>{checked_at}</span>
      <strong>Feed last imported</strong><span>{last_imported}</span>
      <strong>Pending candidates</strong><span>{len(rows)}</span>
    </div>
  </header>
  <main>
    {body}
  </main>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render a sanitized, review-only HTML packet for current Awin feed image candidates."
    )
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        rendered = render_html(load_json(args.candidates))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"DUFYND feed image visual review written: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
