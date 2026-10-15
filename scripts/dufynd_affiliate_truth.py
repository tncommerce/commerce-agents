"""Read-only, evidence-bound partner projection; never authorizes activation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError

EVIDENCE_KEY = "affiliate.partner_evidence.v1"
STATES = Literal[
    "APPLIED",
    "PENDING",
    "APPROVED",
    "REJECTED",
    "FEED_READY",
    "TRACKING_READY",
    "PRODUCT_READY",
    "OFFER_CURRENT",
    "RIGHTS_APPROVED",
    "RIGHTS_HOLD",
    "EXTERNAL_HOLD",
]
MAX_AGE_HOURS = {"FEED_READY": 72, "OFFER_CURRENT": 72}
ID_PATTERN = r"^[A-Za-z0-9._:-]{1,80}$"


class PartnerEvidence(BaseModel):
    """Source verification time is not the later ingestion or observation time."""

    model_config = ConfigDict(extra="forbid", strict=True)
    merchant_id: str = Field(pattern=ID_PATTERN)
    status: STATES
    verified_at: AwareDatetime
    expires_at: AwareDatetime | None = None
    source_kind: Literal[
        "network", "network_email", "merchant_email", "project_verification", "owner_report"
    ]
    evidence_ref: str = Field(pattern=r"^(repo|db|mail|network|owner):[A-Za-z0-9._:/#-]{1,200}$")
    product_id: str | None = Field(default=None, pattern=ID_PATTERN)
    gtin: str | None = Field(default=None, pattern=r"^[0-9]{8,14}$")
    tracking_strategy: Literal["feed", "product_deeplink"] | None = None
    landing_verified: bool = False
    public_page_verified: bool = False
    release_approved: bool = False
    public_offer_verified: bool = False
    price_eur: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    shipping_eur: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    in_stock: bool = False
    image_used: bool | None = None
    asset_ref: str | None = Field(default=None, pattern=ID_PATTERN)


def parse_fact(value: Any) -> PartnerEvidence:
    # JSON-mode accepts ISO timestamps while retaining strict booleans/numbers.
    import json

    return PartnerEvidence.model_validate_json(json.dumps(value, allow_nan=False))


def _fresh(fact: PartnerEvidence, now: datetime) -> bool:
    end = fact.verified_at + timedelta(hours=MAX_AGE_HOURS.get(fact.status, 720))
    if fact.expires_at is not None:
        end = min(end, fact.expires_at)
    return fact.verified_at <= now <= end


def _latest(facts: list[PartnerEvidence], status: str, product: str | None = None):
    candidates = [f for f in facts if f.status == status and f.product_id == product]
    if not candidates:
        return None
    newest = max(f.verified_at for f in candidates)
    latest = [f for f in candidates if f.verified_at == newest]
    # Conflicting same-time observations cannot be resolved by input ordering.
    values = {f.model_dump_json(exclude={"evidence_ref"}) for f in latest}
    return latest[0] if len(values) == 1 else None


def build_partner_truth(
    partners: list[dict[str, Any]], records: list[Any], *, now: datetime
) -> dict[str, Any]:
    if now.tzinfo is None:
        raise ValueError("Timezone-aware evaluation time required")
    now = now.astimezone(UTC)
    facts: list[PartnerEvidence] = []
    invalid: set[str] = set()
    invalid_unbound = False
    if not isinstance(records, list) or len(records) > 2000:
        records, invalid_unbound = [], True
    for record in records:
        try:
            fact = parse_fact(record)
            if fact.verified_at > now:
                raise ValueError("Future evidence")
            facts.append(fact)
        except (ValidationError, ValueError, TypeError):
            merchant = record.get("merchant_id") if isinstance(record, dict) else None
            if isinstance(merchant, str):
                invalid.add(merchant)
            else:
                invalid_unbound = True
    ids = {str(p.get("merchant_id")) for p in partners if p.get("merchant_id")}
    ids.update(f.merchant_id for f in facts)
    registry = {str(p.get("merchant_id")): p for p in partners}
    output = []
    for merchant in sorted(ids):
        legacy = registry.get(merchant, {})
        all_facts = [f for f in facts if f.merchant_id == merchant]
        trusted = [f for f in all_facts if f.source_kind != "owner_report"]
        approval = _latest(trusted, "APPROVED")
        # Merchant feed letters are not proof of network membership.
        approved = bool(
            approval
            and approval.source_kind in {"network", "network_email", "project_verification"}
            and _fresh(approval, now)
        )
        approval_time = (
            approval.verified_at if approval and approved else datetime.min.replace(tzinfo=UTC)
        )
        rejected = legacy.get("status") == "rejected" or bool(
            any(f.status == "REJECTED" and f.verified_at >= approval_time for f in trusted)
        )
        hold = any(
            f.status == "EXTERNAL_HOLD"
            or (
                f.source_kind == "owner_report"
                and f.status == "REJECTED"
                and f.verified_at >= approval_time
            )
            for f in all_facts
        )
        malformed = invalid_unbound or merchant in invalid
        feed = _latest(trusted, "FEED_READY")
        feed_ready = bool(approved and feed and _fresh(feed, now))
        tracking_ready = False
        products = []
        product_ids = sorted({f.product_id for f in all_facts if f.product_id})
        for product_id in product_ids:
            p = _latest(trusted, "PRODUCT_READY", product_id)
            t = _latest(trusted, "TRACKING_READY", product_id)
            o = _latest(trusted, "OFFER_CURRENT", product_id)
            rights = _latest(trusted, "RIGHTS_APPROVED", product_id)
            rights_hold = _latest(trusted, "RIGHTS_HOLD", product_id)
            tracked = bool(
                approved
                and t
                and _fresh(t, now)
                and t.gtin
                and t.landing_verified
                and (
                    t.tracking_strategy == "product_deeplink"
                    or (t.tracking_strategy == "feed" and feed_ready)
                )
            )
            tracking_ready = tracking_ready or tracked
            product_ready = bool(
                tracked
                and p
                and _fresh(p, now)
                and p.gtin == t.gtin
                and p.public_page_verified
                and p.release_approved
                and p.image_used is not None
            )
            image_allowed = bool(
                p
                and (
                    p.image_used is False
                    or (
                        p.asset_ref
                        and rights
                        and _fresh(rights, now)
                        and rights.asset_ref == p.asset_ref
                        and rights.gtin == p.gtin
                        and (not rights_hold or rights.verified_at > rights_hold.verified_at)
                    )
                )
            )
            offer_ready = bool(
                product_ready
                and o
                and _fresh(o, now)
                and o.gtin == p.gtin
                and o.price_eur is not None
                and o.shipping_eur is not None
                and o.in_stock
                and o.public_offer_verified
            )
            blockers = []
            if not tracked:
                blockers.append("product_tracking_not_verified")
            if not product_ready:
                blockers.append("exact_public_product_not_verified")
            if not image_allowed:
                blockers.append("rights_hold")
            if not offer_ready:
                blockers.append("fresh_public_in_stock_offer_not_verified")
            if rejected or hold or malformed:
                blockers.append("partner_hold")
            products.append(
                {
                    "product_id": product_id,
                    "product_ready": product_ready and not (rejected or hold or malformed),
                    "revenue_ready": offer_ready
                    and image_allowed
                    and not (rejected or hold or malformed),
                    "blockers": blockers,
                }
            )
        primary = "UNKNOWN"
        if any(_fresh(f, now) and f.status == "APPLIED" for f in trusted):
            primary = "APPLIED"
        if any(_fresh(f, now) and f.status == "PENDING" for f in trusted):
            primary = "PENDING"
        if approved:
            primary = "APPROVED"
        if feed_ready:
            primary = "FEED_READY"
        if tracking_ready:
            primary = "TRACKING_READY"
        if any(p["product_ready"] for p in products):
            primary = "PRODUCT_READY"
        if any(p["revenue_ready"] for p in products):
            primary = "REVENUE_READY"
        ready_products = [p for p in products if p["product_ready"]]
        if (
            approved
            and ready_products
            and all("rights_hold" in p["blockers"] for p in ready_products)
        ):
            primary = "RIGHTS_HOLD"
        if hold:
            primary = "EXTERNAL_HOLD"
        if malformed:
            primary = "UNKNOWN"
        if rejected:
            primary = "REJECTED"
        output.append(
            {
                "merchant_id": merchant,
                "primary_status": primary,
                "legacy_claim": legacy.get("status", "unknown"),
                "invalid_evidence": malformed,
                "products": products,
                "stage_evidence": [
                    {
                        "status": f.status,
                        "product_id": f.product_id,
                        "verified_at": f.verified_at.isoformat(),
                        "evidence_ref": f.evidence_ref,
                        "source_kind": f.source_kind,
                        "stale": not _fresh(f, now),
                    }
                    for f in sorted(
                        all_facts, key=lambda f: (f.status, f.product_id or "", f.verified_at)
                    )
                ],
                "automatic_application_allowed": False,
                "automatic_commerce_planning_allowed": primary
                in {"APPROVED", "FEED_READY", "TRACKING_READY", "PRODUCT_READY", "REVENUE_READY"},
                "activation_allowed": False,
                "next_safe_action": "read_evidence_only"
                if rejected
                else "verify_missing_or_stale_evidence",
            }
        )
    return {
        "version": 1,
        "observed_at": now.isoformat(),
        "read_only": True,
        "evidence_key": EVIDENCE_KEY,
        "partners": output,
        "commerce_plan": [
            {"merchant_id": p["merchant_id"], "action": "prepare_evidence_bound_draft"}
            for p in output
            if p["automatic_commerce_planning_allowed"]
        ],
        "revenue_ready_means": "technical_purchase_path_not_verified_sales",
        "production_writes": False,
    }


def context_partner_truth(
    context: dict[str, Any], *, now: datetime | None = None
) -> dict[str, Any]:
    """Use the existing master-status store; no second database or automatic write."""
    master = context.get("master_status")
    if master is None:
        master = []
    if not isinstance(master, list) or any(not isinstance(r, dict) for r in master):
        master = [{"key": EVIDENCE_KEY, "value": None}]
    entries = [r for r in master if r.get("key") == EVIDENCE_KEY]
    records: Any = []
    if len(entries) == 1:
        value = entries[0].get("value", {})
        records = (
            value.get("records") if isinstance(value, dict) and value.get("version") == 1 else None
        )
    elif entries:
        records = None
    projection = build_partner_truth(
        context.get("affiliate_partners", []), records, now=now or datetime.now(UTC)
    )
    # Every page reloads context. A volatile wall clock would change its hash on
    # every request, preventing completion of multi-page evidence reads.
    projection.pop("observed_at")
    return projection
