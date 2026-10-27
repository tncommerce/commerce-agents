"""Generate a safe, offline review of four *unpublished* DUFYND originals.

A source image, a mapped GTIN and a publisher-owned Awin product link are
necessary for the reviewer, but are NOT an image publication approval or a
current merchant price/stock/affiliate activation. No network request is made.
"""

from __future__ import annotations

import argparse
import html
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "examples/retail/data"
PUBLIC = ROOT / "examples/retail/storefront-web/lib/generated"
MANIFEST = ROOT / "artifacts/dufynd-staging-photo-wave-20261027/exact-identity-source-review.json"
IMAGE = re.compile(
    r"/media/catalog/product/(?:[a-z0-9]/){2}([0-9]+)_([0-9]+)_[0-9]+\.png"
)
HASH = re.compile(r"[0-9a-f]{64}")
NUMERIC = re.compile(r"[0-9]{1,16}")
RIGHTS_BASIS = "awin_top_parfuemerie_feed_materials_20260928"


def _gtin(value: object) -> str:
    token = str(value or "")
    if not token.isdigit() or not (8 <= len(token) <= 14):
        raise ValueError("missing_or_invalid_exact_gtin")
    return token.lstrip("0") or "0"


def _timestamp(value: object, *, now: datetime, horizon: timedelta) -> str:
    if not isinstance(value, str):
        raise ValueError("unverified_source_timestamp")
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("invalid_source_timestamp") from error
    if date.tzinfo is None or not timedelta(0) <= now - date.astimezone(UTC) <= horizon:
        raise ValueError("expired_future_or_unzoned_source")
    return date.astimezone(UTC).isoformat()


def _image_source(url: str, sku: str, gtin: str) -> None:
    u = urlsplit(url)
    if u.scheme != "https" or u.netloc != "www.topparfuemerie.de" or u.query or u.fragment:
        raise ValueError("unlicensed_or_untrusted_image_source")
    m = IMAGE.fullmatch(u.path)
    if not m or m.group(1) != sku or _gtin(m.group(2)) != _gtin(gtin):
        raise ValueError("image_sku_gtin_mismatch")


def _original_awin_route(url: str, aw_product_id: str) -> None:
    u = urlsplit(url)
    if (u.scheme, u.netloc, u.path, u.fragment) != (
        "https", "www.awin1.com", "/pclick.php", ""
    ):
        raise ValueError("unexpected_awin_route")
    try:
        pairs = parse_qsl(u.query, keep_blank_values=True, strict_parsing=True)
    except ValueError as error:
        raise ValueError("invalid_awin_query") from error
    if len(pairs) != 3 or dict(pairs) != {
        "p": aw_product_id, "a": "3099222", "m": "31081"
    }:
        raise ValueError("awin_publisher_product_mismatch")


def build_private_review(
    manifest: dict,
    staging: dict,
    public: dict,
    mappings: dict,
    originals: list[dict],
    partners: dict,
    rights: dict,
    *,
    now: datetime,
) -> dict:
    """Fail the whole review on any source, identity, or publication-gate error."""
    if now.tzinfo is None:
        raise ValueError("aware_review_time_required")
    clock = now.astimezone(UTC)
    source = manifest.get("source", {})
    if (
        manifest.get("status")
        != "SOURCE_IMAGE_AND_GTIN_CORROBORATED_PRIVATE_REVIEW_ONLY_NOT_PUBLISHED"
        or source.get("official_feed_workflow_run") != 40472385765
        or source.get("original_image_byte_receipt_run") != 40473278522
        or source.get("advertiser_id") != "31081"
        or source.get("feed_id") != "91379"
        or source.get("active") is not True
        or not HASH.fullmatch(str(source.get("feed_sha256", "")))
        or manifest.get("rights", {}).get("basis") != RIGHTS_BASIS
    ):
        raise ValueError("source_provenance_or_rights_manifest_unverified")
    feed_date = _timestamp(
        source.get("checked_at"), now=clock, horizon=timedelta(days=7)
    )
    byte_date = _timestamp(
        source.get("original_image_byte_receipt_date"),
        now=clock, horizon=timedelta(days=7),
    )
    license_rows = [
        x for x in rights.get("entries", [])
        if x.get("rights_basis_id") == RIGHTS_BASIS
        and x.get("merchant_id") == "top-parfuemerie"
        and x.get("advertiser_id") == "31081"
        and x.get("program_status") == "approved"
        and x.get("rights_status") == "verified_for_publisher_service"
        and x.get("asset_scope")
        == "unaltered_advertiser_materials_from_official_awin_product_feed"
    ]
    if len(license_rows) != 1:
        raise ValueError("active_official_feed_image_license_required")
    publishers = [
        p for p in partners.get("partners", [])
        if p.get("merchant_id") == "top-parfuemerie"
        and p.get("status") == "active_product_deeplink_only"
    ]
    if len(publishers) != 1:
        raise ValueError("active_publisher_program_required")

    public_ids = {p.get("product_id") for p in public.get("products", [])}
    already_originals = {p.get("product_id") for p in originals}
    staged = {p.get("product_id"): p for p in staging.get("products", [])}
    known_mappings = {}
    for m in mappings.get("mappings", []):
        if m.get("product_id"):
            known_mappings.setdefault(m["product_id"], []).append(m)

    entries = manifest.get("newly_selected_for_visual_and_byte_qa")
    if not isinstance(entries, list) or len(entries) != 4:
        raise ValueError("exact_four_private_source_rows_required")
    items, used = [], set()
    for entry in entries:
        pid = entry.get("product_id")
        item = entry.get("product", {})
        feed = entry.get("official_feed", {})
        gate = entry.get("review_gates", {})
        original = staged.get(pid)
        if (
            not isinstance(pid, str)
            or pid in used
            or pid in public_ids
            or pid in already_originals
            or not isinstance(original, dict)
        ):
            raise ValueError("staging_only_unique_unpublished_product_required")
        used.add(pid)
        if (
            item.get("brand") != original.get("brand")
            or item.get("name") != original.get("name")
            or item.get("concentration") != original.get("concentration")
            or type(item.get("volume_ml")) is not int
            or item["volume_ml"] != original.get("volume_ml")
            or not original.get("validation", {}).get("blockers")
        ):
            raise ValueError("unverified_staging_variant_identity")
        matched_gtins = {_gtin(m.get("gtin") or m.get("ean")) for m in known_mappings.get(pid, [])}
        if matched_gtins != {_gtin(item.get("canonical_historical_gtin"))}:
            raise ValueError("contradictory_historical_gtin")
        sku = str(feed.get("merchant_sku") or "")
        awid = str(feed.get("awin_product_id") or "")
        if (
            not NUMERIC.fullmatch(sku)
            or not NUMERIC.fullmatch(awid)
            or feed.get("advertiser_id") != "31081"
            or feed.get("feed_id") != "91379"
            or feed.get("publisher_id") != "3099222"
            or not HASH.fullmatch(str(feed.get("source_row_hash", "")))
        ):
            raise ValueError("invalid_official_product_source")
        url = feed.get("image_url", "")
        if not isinstance(url, str):
            raise ValueError("invalid_image_url_type")
        _image_source(url, sku, item["canonical_historical_gtin"])
        _original_awin_route(str(feed.get("original_feed_deeplink", "")), awid)
        product_page = urlsplit(str(feed.get("product_url", "")))
        if (product_page.scheme != "https" or product_page.netloc != "www.topparfuemerie.de"
                or product_page.query or product_page.fragment or not product_page.path.startswith("/")):
            raise ValueError("unexpected_merchant_product_url")
        if (
            gate.get("source_image_download_verified") is not True
            or gate.get("source_png_unchanged") is not True
            or gate.get("owner_visual_acceptance") is not False
            or gate.get("public_image_allowed") is not False
            or gate.get("new_affiliate_offer_activated") is not False
            or gate.get("new_profile_published") is not False
            or gate.get("merchant_selected_size_verified_now") is not False
            or gate.get("merchant_current_price_stock_shipping_verified") is not False
            or gate.get("source_image_bytes_sha256") is None
            or not HASH.fullmatch(str(gate.get("source_image_bytes_sha256")))
            or not 1_000 <= gate.get("byte_count", 0) <= 2_000_000
            or not 150 <= gate.get("source_png_dimensions", {}).get("width", 0) <= 2000
            or not 150 <= gate.get("source_png_dimensions", {}).get("height", 0) <= 2000
        ):
            raise ValueError("source_bytes_or_owner_publication_gate_failed")
        _timestamp(
            gate.get("source_verified_at_utc"), now=clock, horizon=timedelta(days=7)
        )
        items.append({
            "product_id": pid,
            "brand": item["brand"],
            "name": item["name"],
            "concentration": item["concentration"],
            "volume_ml": item["volume_ml"],
            "gtin": item["canonical_historical_gtin"],
            "merchant_sku": sku,
            "awin_product_id": awid,
            "image_url": url,
            "image_sha256": gate["source_image_bytes_sha256"],
            "image_dimensions": gate["source_png_dimensions"],
            "scent_family": original.get("fragrance_profile", {}).get("scent_family"),
            "key_notes": original.get("fragrance_profile", {}).get("key_notes", []),
            "merchants_historically_mapped": len(known_mappings.get(pid, [])),
            "status": "ORIGINAL_SOURCE_VERIFIED_OWNER_REVIEW_REQUIRED",
            "price_eur": None,
            "stock_confirmed": False,
            "discount_claim_allowed": False,
            "merchant_clickout_enabled": False,
            "photo_publication_allowed": False,
            "catalog_publication_allowed": False,
        })
    return {
        "schema_version": 1,
        "status": "PRIVATE_STAGING_REVIEW_NO_PRODUCTION_OR_MERCHANT_ACTIVATION",
        "official_feed_checked_at": feed_date,
        "png_bytes_checked_at": byte_date,
        "image_rights_basis": RIGHTS_BASIS,
        "items": items,
        "totals": {
            "source_verified_originals": len(items),
            "approved_public_images": 0,
            "new_purchasable_offers": 0,
            "new_public_profiles": 0,
            "affiliate_clickouts": 0,
        },
    }


def render_html(review: dict) -> str:
    """Self-contained local preview; no merchant/affiliate requests or JS."""
    cards = []
    for p in review["items"]:
        def esc(x: object) -> str:
            return html.escape(str(x), quote=True)
        notes = ", ".join(str(n) for n in p["key_notes"][:5])
        cards.append(
            '<article class="card">'
            '<div class="stage"><img loading="lazy" decoding="async" '
            f'width="{p["image_dimensions"]["width"]}" '
            f'height="{p["image_dimensions"]["height"]}" '
            f'src="{esc(p["image_url"])}" '
            f'alt="Offizielles Originalfoto {esc(p["brand"])} {esc(p["name"])}"></div>'
            '<div class="copy">'
            f'<div class="eyebrow">{esc(p["brand"])}</div>'
            f'<h2>{esc(p["name"])}</h2>'
            f'<p class="variant">{esc(p["concentration"])} · {p["volume_ml"]} ml</p>'
            f'<p class="accord">{esc(p["scent_family"] or "")}</p>'
            f'<p class="notes">Noten: {esc(notes)}</p>'
            f'<p class="evidence">EAN {esc(p["gtin"])} · Händler-SKU {esc(p["merchant_sku"])}'
            f'<br>Originalbild-SHA256: <code>{esc(p["image_sha256"])}</code></p>'
            '<button type="button" disabled>Kein Kaufbutton · Bildprüfung</button></div></article>'
        )
    css = """*{box-sizing:border-box}body{margin:0;background:#0c0e12;color:#ece8e1;
font:15px/1.6 system-ui,sans-serif}.shell{width:min(1220px,94%);margin:auto}
header{padding:35px 0 26px;border-bottom:1px solid #343539;display:flex;
justify-content:space-between;gap:12px;flex-wrap:wrap}
.logo{letter-spacing:.2em;font-weight:850}.chip{font-size:11px;color:#d6b681}
h1{font:normal clamp(32px,5vw,65px)/1.1 Georgia,serif;max-width:840px;margin:35px 0}
.lede{max-width:810px;color:#b9b3a9;margin-bottom:32px}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;margin:0 0 48px}
.card{background:#181b20;min-width:0;border:1px solid #383838}.stage{height:330px;display:flex;
justify-content:center;align-items:center;background:#edeae5;padding:32px}
.stage img{max-height:100%;max-width:100%;height:100%;width:auto;object-fit:contain}
.copy{padding:26px}.eyebrow{font-size:11px;letter-spacing:.12em;color:#d6b681}
h2{font:normal 31px/1.15 Georgia,serif;margin:9px 0}.variant{color:#e0ddd6}
.accord{text-transform:uppercase;font-size:11px;letter-spacing:.12em;color:#d6b681}
.notes{color:#b9b3a9}.evidence{font-size:11px;color:#a2a0a0}
code{overflow-wrap:anywhere}button{margin-top:15px;width:100%;border:1px solid #494c51;
background:#313438;color:#b6b6b6;padding:12px;border-radius:3px}
footer{padding:24px 0 40px;color:#aaa;border-top:1px solid #383838;font-size:12px}
@media(max-width:650px){.grid{grid-template-columns:1fr}.stage{height:315px;padding:26px}}
"""
    return (
        '<!doctype html><html lang="de"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="noindex,nofollow">'
        '<title>DUFYND – Vier neue Originalflakons · interne Prüfung</title>'
        f'<style>{css}</style></head><body><div class="shell">'
        '<header><strong class="logo">DUFYND</strong>'
        '<span class="chip">ORIGINALFOTOS · PRIVATER REVIEW · NICHT LIVE</span></header>'
        '<main><h1>Vier neue Originalflakons.<br>Vier echte Duftprofile.</h1>'
        '<p class="lede">Unveränderte, quellgeprüfte Flakonbilder aus dem offiziellen '
        'Top-Parfümerie-Awin-Feed. Varianten und historische EAN-Abgleiche geprüft. '
        'Noch keine visuelle Freigabe, kein aktueller Händlerpreis und keine Kaufoption.'
        ' Keine Neuveröffentlichung.</p><section class="grid">'
        + "".join(cards)
        + '</section></main><footer>Quelle: Awin-Feed 31081 / 91379, Prüfläufe '
        '#40472385765 und #40473278522 · '
        'Hinweis: Originalbilder werden beim Öffnen direkt vom Händler geladen. '
        'Dieses Dokument speichert keine Zugangsdaten oder Affiliate-Klickziele.'
        '</footer></div></body></html>'
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--format", choices=("json", "html"), default="json")
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    def load(path: Path):
        return json.loads(path.read_text(encoding="utf-8-sig"))
    review = build_private_review(
        load(MANIFEST),
        load(DATA / "scentai_catalog_staging.json"),
        load(PUBLIC / "public-fragrances.json"),
        load(DATA / "merchant_product_mappings.json"),
        load(PUBLIC / "original-photos.json"),
        load(DATA / "merchant_partners.json"),
        load(DATA / "dufynd_affiliate_feed_image_rights.json"),
        now=datetime.now(UTC),
    )
    output = render_html(review) if args.format == "html" else json.dumps(
        review, ensure_ascii=False, indent=2
    ) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
