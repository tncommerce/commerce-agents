from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from scripts.register_scentai_model3d import APPROVABLE_SOURCE_CLASSES, VERIFIED_RIGHTS_STATUS
from scripts.scentai_model3d_guard import normalize_model_url, validated_model_sha256

DEFAULT_CANDIDATES = Path("examples/retail/data/dufynd_model3d_candidates.json")
DEFAULT_PUBLIC_ROOT = Path("examples/retail/storefront-web/public")
DEFAULT_OUTPUT = Path("dufynd-model3d-review.html")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _norm(value: object) -> str:
    return str(value or "").strip()


def review_candidates(payload: dict, public_root: Path) -> list[dict]:
    if _norm(payload.get("status")) != "review_only_not_live":
        raise ValueError("model_candidate_payload_not_review_only")

    reviewed: list[dict] = []
    for candidate in payload.get("candidates", []):
        if _norm(candidate.get("review_status")) != "pending_review":
            continue
        if _norm(candidate.get("role")) != "model_3d":
            raise ValueError("model_candidate_role_invalid")
        if candidate.get("geometry_review_required") is not True:
            raise ValueError("model_geometry_review_contract_missing")
        if candidate.get("exact_variant_verified") is not True:
            raise ValueError("model_exact_variant_not_verified")
        if _norm(candidate.get("proposed_fidelity_status")) != "verified":
            raise ValueError("model_candidate_fidelity_invalid")
        if _norm(candidate.get("source_class")) not in APPROVABLE_SOURCE_CLASSES:
            raise ValueError("model_source_class_not_approvable")

        model_url = normalize_model_url(candidate.get("model_url"))
        actual_sha256 = validated_model_sha256(public_root, model_url)
        expected_sha256 = _norm(candidate.get("model_sha256")).casefold()
        if actual_sha256 != expected_sha256:
            raise ValueError("model_asset_hash_mismatch")

        rights = candidate.get("rights_evidence") or {}
        if _norm(rights.get("rights_status")) != VERIFIED_RIGHTS_STATUS:
            raise ValueError("model_rights_not_verified")
        for field, error in (
            ("commercial_use_allowed", "model_commercial_use_not_allowed"),
            ("public_distribution_allowed", "model_public_distribution_not_allowed"),
            ("interactive_web_display_allowed", "model_interactive_web_display_not_allowed"),
        ):
            if rights.get(field) is not True:
                raise ValueError(error)
        if not _norm(rights.get("rights_basis_id")) or not _norm(rights.get("rights_checked_at")):
            raise ValueError("model_rights_evidence_incomplete")

        reviewed.append(
            {**candidate, "model_url": model_url, "verified_model_sha256": actual_sha256}
        )

    return reviewed


def render_html(candidates: list[dict], *, relative_model_paths: bool = False) -> str:
    cards = []
    for candidate in candidates:
        rights = candidate.get("rights_evidence") or {}
        product = " · ".join(
            part
            for part in (
                _norm(candidate.get("brand")),
                _norm(candidate.get("name")),
                _norm(candidate.get("concentration")),
                _norm(candidate.get("variant")),
            )
            if part
        )
        model_url = _norm(candidate.get("model_url"))
        model_src = model_url.removeprefix("/") if relative_model_paths else model_url
        escaped_model_src = html.escape(model_src, quote=True)
        fields = [
            ("Product ID", candidate.get("product_id")),
            ("Variant", candidate.get("variant")),
            ("Source class", candidate.get("source_class")),
            ("Rights basis", rights.get("rights_basis_id")),
            ("Rights checked", rights.get("rights_checked_at")),
            ("SHA-256", candidate.get("verified_model_sha256")),
            ("Status", "pending_review"),
        ]
        meta = "".join(
            f"<dt>{html.escape(label)}</dt><dd>{html.escape(_norm(value))}</dd>"
            for label, value in fields
        )
        cards.append(
            f"""
            <article class="card">
              <div class="viewer">
                <model-viewer
                  src="{escaped_model_src}"
                  alt="{html.escape(product, quote=True)}"
                  camera-controls
                  auto-rotate
                  auto-rotate-delay="1200"
                  rotation-per-second="6deg"
                  interaction-prompt="auto"
                  shadow-intensity="1"
                  shadow-softness="0.8"
                  exposure="1.05"
                ></model-viewer>
              </div>
              <div class="info">
                <div class="eyebrow">DUFYND TRUE 3D · HUMAN REVIEW REQUIRED</div>
                <h2>{html.escape(product)}</h2>
                <p class="warning">NOT LIVE · PENDING REVIEW. Prüfe Form, Proportionen, Sprühkopf, Schrift, Farben, Materialien und alle Marken-/Flakondetails gegen die exakte Produktvariante.</p>
                <dl>{meta}</dl>
                <p class="note">Diese Seite kann kein Modell freigeben. Die Aktivierung bleibt an die separate explizite Human-Approval-Pipeline gebunden.</p>
              </div>
            </article>
            """
        )

    empty = (
        '<section class="empty"><h2>Keine 3D-Kandidaten in Prüfung</h2>'
        "<p>Die Queue ist review-only und enthält aktuell keinen pending_review-Kandidaten.</p></section>"
        if not cards
        else ""
    )
    return f"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src https://unpkg.com; style-src 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; child-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'">
<title>DUFYND 3D Model Review</title>
<script type="module" src="https://unpkg.com/@google/model-viewer@4.3.1/dist/model-viewer.min.js"></script>
<style>
:root {{ color-scheme: dark; font-family: Inter, ui-sans-serif, system-ui, sans-serif; background:#08090b; color:#f7f2e8; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; min-height:100vh; background:radial-gradient(circle at 75% 10%,#312512 0,transparent 28rem),linear-gradient(145deg,#08090b,#111014); }}
main {{ width:min(1180px,calc(100% - 28px)); margin:0 auto; padding:32px 0 60px; }}
header {{ margin-bottom:24px; }}
h1 {{ margin:0; font-size:clamp(28px,5vw,52px); letter-spacing:-.045em; }}
header p {{ color:#b8b0a3; max-width:760px; line-height:1.6; }}
.card {{ display:grid; grid-template-columns:minmax(0,1.15fr) minmax(320px,.85fr); overflow:hidden; border:1px solid rgba(255,255,255,.09); border-radius:28px; background:rgba(17,16,20,.88); box-shadow:0 30px 80px rgba(0,0,0,.4); margin:22px 0; }}
.viewer {{ min-height:620px; background:radial-gradient(circle at 50% 38%,rgba(218,174,89,.15),transparent 32%),linear-gradient(145deg,#101113,#07080a); }}
model-viewer {{ width:100%; height:100%; min-height:620px; --poster-color:transparent; }}
.info {{ padding:34px; align-self:center; }}
.eyebrow {{ color:#d9b96f; font-size:10px; font-weight:800; letter-spacing:.16em; }}
h2 {{ font-size:30px; line-height:1.05; margin:10px 0 20px; }}
.warning {{ border:1px solid rgba(230,190,104,.22); background:rgba(184,137,52,.08); padding:14px; border-radius:14px; color:#ead9b7; line-height:1.55; }}
dl {{ display:grid; grid-template-columns:120px 1fr; gap:9px 14px; margin-top:24px; font-size:12px; }}
dt {{ color:#857d72; }}
dd {{ margin:0; overflow-wrap:anywhere; }}
.note {{ color:#91897e; font-size:11px; line-height:1.55; margin-top:24px; }}
.empty {{ border:1px solid rgba(255,255,255,.09); border-radius:24px; padding:28px; background:rgba(255,255,255,.035); }}
@media(max-width:760px) {{ .card {{ grid-template-columns:1fr; }} .viewer,model-viewer {{ min-height:420px; }} .info {{ padding:22px; }} dl {{ grid-template-columns:100px 1fr; }} }}
@media(prefers-reduced-motion:reduce) {{ model-viewer {{ --min-hotspot-opacity:0; }} }}
</style>
</head>
<body>
<main>
<header>
  <div class="eyebrow">DUFYND · REVIEW ONLY</div>
  <h1>True 3D Geometry Review</h1>
  <p>Interaktive Vorprüfung rights-cleared GLB-Kandidaten. Kein Kandidat wird durch diese Ansicht freigegeben oder live geschaltet.</p>
</header>
{"".join(cards)}
{empty}
</main>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a review-only DUFYND 3D model packet.")
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--public-root", type=Path, default=DEFAULT_PUBLIC_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--relative-model-paths", action="store_true")
    args = parser.parse_args()

    try:
        candidates = review_candidates(load_json(args.candidates), args.public_root)
        rendered = render_html(candidates, relative_model_paths=args.relative_model_paths)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"DUFYND 3D review packet | candidates={len(candidates)} | output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
