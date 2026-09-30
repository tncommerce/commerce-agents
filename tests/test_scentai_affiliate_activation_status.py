from __future__ import annotations

from scripts.evaluate_scentai_affiliate_activation import (
    build_state_report,
)


def test_affiliate_state_report_uses_control_plane_summary_schema() -> None:
    programs = {
        "network": "Awin",
        "applications": [
            {
                "merchant_id": "douglas",
                "program": "Douglas_DE",
                "status": "applied",
            },
            {
                "merchant_id": "flaconi",
                "program": "Flaconi DE",
                "status": "approved",
            },
        ],
        "other_networks": [],
    }

    report = build_state_report(
        programs,
        generated_at="2026-09-19T10:00:00+00:00",
    )

    assert report["generated_at"] == "2026-09-19T10:00:00+00:00"
    assert report["summary"] == {
        "programs": 2,
        "approved": 1,
        "active": 0,
        "pending": 2,
        "rejected": 0,
        "ready_for_user_approval": 0,
        "merchant_homepage_tracking_active": 0,
    }
    assert report["program_count"] == 2
    assert report["live_program_count"] == 0

    flaconi = next(row for row in report["programs"] if row["merchant_id"] == "flaconi")
    assert flaconi["activation_state"] == "approved_credentials_pending"
    assert flaconi["live_routing_allowed"] is False
    assert flaconi["routing_scope"] == "none"
    assert flaconi["next_action"] == "verify_credentials"


def test_verified_active_partner_is_active_only_at_merchant_homepage_scope() -> None:
    programs = {
        "network": "Awin",
        "applications": [
            {
                "merchant_id": "perfumetrader",
                "program": "Perfumetrader DE",
                "status": "approved",
                "tracking_strategy": "verified_awin_partner_homepage_link",
            }
        ],
        "other_networks": [],
    }
    partners = {
        "partners": [
            {
                "merchant_id": "perfumetrader",
                "status": "active",
                "affiliate_url": "https://www.awin1.com/cread.php?awinmid=11672",
                "last_verified_at": "2026-09-21T13:04:00Z",
            }
        ]
    }

    report = build_state_report(
        programs,
        generated_at="2026-09-22T07:00:00+00:00",
        merchant_partners=partners,
    )

    assert report["summary"]["active"] == 1
    assert report["summary"]["merchant_homepage_tracking_active"] == 1
    row = report["programs"][0]
    assert row["activation_state"] == "active"
    assert row["live_routing_allowed"] is True
    assert row["routing_scope"] == "merchant_homepage_only"
    assert row["product_offer_activation_independent"] is True
    assert row["blockers"] == []
    assert row["next_action"] == "maintain_partner_health"


def test_active_partner_registry_cannot_override_unapproved_program() -> None:
    programs = {
        "network": "Awin",
        "applications": [
            {
                "merchant_id": "merchant",
                "program": "Merchant DE",
                "status": "applied",
                "tracking_strategy": "verified_awin_partner_homepage_link",
            }
        ],
        "other_networks": [],
    }
    partners = {
        "partners": [
            {
                "merchant_id": "merchant",
                "status": "active",
                "affiliate_url": "https://example.test/tracked",
                "last_verified_at": "2026-09-21T13:04:00Z",
            }
        ]
    }

    report = build_state_report(programs, merchant_partners=partners)
    row = report["programs"][0]

    assert row["activation_state"] == "applied"
    assert row["live_routing_allowed"] is False
    assert row["merchant_homepage_tracking_active"] is False


def test_active_partner_requires_verified_tracking_strategy() -> None:
    programs = {
        "network": "Awin",
        "applications": [
            {
                "merchant_id": "merchant",
                "program": "Merchant DE",
                "status": "approved",
            }
        ],
        "other_networks": [],
    }
    partners = {
        "partners": [
            {
                "merchant_id": "merchant",
                "status": "active",
                "affiliate_url": "https://example.test/tracked",
                "last_verified_at": "2026-09-21T13:04:00Z",
            }
        ]
    }

    report = build_state_report(programs, merchant_partners=partners)
    row = report["programs"][0]

    assert row["activation_state"] == "approved_credentials_pending"
    assert row["live_routing_allowed"] is False


def test_rejected_program_is_not_counted_as_pending() -> None:
    programs = {
        "network": "Awin",
        "applications": [
            {
                "merchant_id": "open-merchant",
                "program": "Open Merchant",
                "status": "applied",
            },
            {
                "merchant_id": "rejected-merchant",
                "program": "Rejected Merchant",
                "status": "rejected",
            },
        ],
        "other_networks": [],
    }

    report = build_state_report(programs)

    assert report["summary"]["programs"] == 2
    assert report["summary"]["pending"] == 1
    assert report["summary"]["rejected"] == 1
    rejected = next(row for row in report["programs"] if row["merchant_id"] == "rejected-merchant")
    assert rejected["activation_state"] == "rejected"
    assert rejected["next_action"] == "none"


def test_verified_product_deeplink_waits_for_explicit_user_approval() -> None:
    programs = {
        "network": "Awin",
        "applications": [],
        "other_networks": [
            {
                "network": "CJ Affiliate",
                "merchant_id": "notino",
                "program": "Notino",
                "status": "approved",
                "tracking_strategy": "verified_cj_product_deeplink",
                "tracked_product_url_verified": True,
                "redirect_dry_run_passed": True,
                "verified_product_scope": ["SC-LATTAFA-ECLAIRE-EDP-100"],
            }
        ],
    }

    report = build_state_report(programs)
    row = report["programs"][0]

    assert report["summary"]["ready_for_user_approval"] == 1
    assert report["summary"]["active"] == 0
    assert row["activation_state"] == "ready_for_user_approval"
    assert row["live_routing_allowed"] is False
    assert row["routing_scope"] == "verified_product_only_pending_activation"
    assert row["blockers"] == ["user_approval_not_recorded"]
    assert row["next_action"] == "request_explicit_user_approval"


def test_verified_product_deeplink_becomes_active_after_scoped_user_approval() -> None:
    programs = {
        "network": "Awin",
        "applications": [],
        "other_networks": [
            {
                "network": "CJ Affiliate",
                "merchant_id": "notino",
                "program": "Notino",
                "status": "approved",
                "tracking_strategy": "verified_cj_product_deeplink",
                "tracked_product_url_verified": True,
                "redirect_dry_run_passed": True,
                "verified_product_scope": ["SC-LATTAFA-ECLAIRE-EDP-100"],
                "live_activation_approved": True,
                "live_activation_approved_at": "2026-09-30T16:16:00Z",
                "live_activation_scope": "verified_product_only",
                "live_activation_products": ["SC-LATTAFA-ECLAIRE-EDP-100"],
            }
        ],
    }

    report = build_state_report(programs)
    row = report["programs"][0]

    assert report["summary"]["ready_for_user_approval"] == 0
    assert report["summary"]["active"] == 1
    assert report["summary"]["merchant_homepage_tracking_active"] == 0
    assert row["activation_state"] == "active"
    assert row["live_routing_allowed"] is True
    assert row["routing_scope"] == "verified_product_only"
    assert row["blockers"] == []
    assert row["next_action"] == "maintain_product_deeplink_health"


def test_product_scoped_activation_cannot_expand_beyond_verified_scope() -> None:
    programs = {
        "network": "Awin",
        "applications": [],
        "other_networks": [
            {
                "network": "CJ Affiliate",
                "merchant_id": "notino",
                "program": "Notino",
                "status": "approved",
                "tracking_strategy": "verified_cj_product_deeplink",
                "tracked_product_url_verified": True,
                "redirect_dry_run_passed": True,
                "verified_product_scope": ["SC-LATTAFA-ECLAIRE-EDP-100"],
                "live_activation_approved": True,
                "live_activation_scope": "verified_product_only",
                "live_activation_products": [
                    "SC-LATTAFA-ECLAIRE-EDP-100",
                    "SC-XERJOFF-NAXOS-100",
                ],
            }
        ],
    }

    row = build_state_report(programs)["programs"][0]

    assert row["activation_state"] == "ready_for_user_approval"
    assert row["live_routing_allowed"] is False
