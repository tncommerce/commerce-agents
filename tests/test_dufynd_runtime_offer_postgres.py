"""Real SQL/RLS/trigger test against CI's disposable PostgreSQL service only."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

DSN = os.getenv("DUFYND_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="isolated CI PostgreSQL only")
MIGRATION = Path("supabase/migrations/20261023221100_dufynd_runtime_offer_snapshots_v1.sql")
TABLE = "public.dufynd_runtime_offer_snapshots_v1"
AUDIT = "public.dufynd_runtime_offer_snapshot_audit_v1"


@pytest.fixture(scope="module", autouse=True)
def create_schema():
    if not DSN:
        yield
        return
    import psycopg

    with psycopg.connect(DSN, autocommit=True) as connection:
        for role in ("anon", "authenticated", "service_role"):
            connection.execute(
                f"""do $$
                begin
                  if not exists(select 1 from pg_roles where rolname='{role}') then
                    create role {role} nologin;
                  end if;
                end
                $$;"""
            )
        # Supabase's server-side service_role bypasses RLS by design.
        # Reproduce that only inside the disposable CI PostgreSQL service.
        connection.execute("alter role service_role bypassrls")
        connection.execute(MIGRATION.read_text(encoding="utf-8"))
    yield


@pytest.fixture
def db():
    import psycopg

    with psycopg.connect(DSN) as connection:
        yield connection
        connection.rollback()


def observation(offer_id: str = "ci-demo-verified-100") -> dict:
    return {
        "offer_id": offer_id,
        "product_id": "SC-CI-EXACT-100",
        "merchant_id": "ci-merchant",
        "merchant_product_id": "CI-100-EDP",
        "identity_sha256": "a" * 64,
        "currency": "EUR",
        "price": "100.00",
        "shipping_cost": "4.99",
        "in_stock": True,
        "verified_at": datetime.now(UTC) - timedelta(minutes=30),
        "decision": "verified",
        "source_type": "official_network_feed",
        "source_ref": "ci-synthetic-only-no-feed",
        "evidence_sha256": "b" * 64,
    }


def insert(db, row: dict) -> None:
    watermark_column = ",source_watermark_at" if "source_watermark_at" in row else ""
    watermark_value = ",%(source_watermark_at)s" if "source_watermark_at" in row else ""
    db.execute(
        f"""insert into {TABLE}
        (offer_id,product_id,merchant_id,merchant_product_id,identity_sha256,
         currency,price,shipping_cost,in_stock,verified_at,decision,
         source_type,source_ref,evidence_sha256{watermark_column})
        values
        (%(offer_id)s,%(product_id)s,%(merchant_id)s,%(merchant_product_id)s,
         %(identity_sha256)s,%(currency)s,%(price)s,%(shipping_cost)s,
         %(in_stock)s,%(verified_at)s,%(decision)s,%(source_type)s,
         %(source_ref)s,%(evidence_sha256)s{watermark_value})""",
        row,
    )


def test_live_sql_rls_privileges_are_private(db):
    assert db.execute(
        f"select relrowsecurity from pg_class where oid='{TABLE}'::regclass"
    ).fetchone()[0]
    assert db.execute(
        f"select relrowsecurity from pg_class where oid='{AUDIT}'::regclass"
    ).fetchone()[0]
    for role in ("anon", "authenticated"):
        assert not db.execute(
            f"select has_table_privilege(%s, '{TABLE}', 'select')", (role,)
        ).fetchone()[0]
        assert not db.execute(
            f"select has_table_privilege(%s, '{TABLE}', 'insert')", (role,)
        ).fetchone()[0]
        assert not db.execute(
            f"select has_table_privilege(%s, '{AUDIT}', 'select')", (role,)
        ).fetchone()[0]
    assert db.execute(
        f"select has_table_privilege('service_role','{TABLE}','select,insert,update')"
    ).fetchone()[0]
    assert not db.execute(
        f"select has_table_privilege('service_role','{TABLE}','delete')"
    ).fetchone()[0]


def test_sql_updates_price_and_audits_without_renewing_source_time(db):
    row = observation()
    db.execute("set local role service_role")
    insert(db, row)
    newer = row["verified_at"] + timedelta(minutes=10)
    db.execute(
        f"""update {TABLE}
        set price=%s, shipping_cost=%s, verified_at=%s
        where offer_id=%s""",
        ("94.30", "0.00", newer, row["offer_id"]),
    )
    updated = db.execute(
        f"select price, shipping_cost, verified_at from {TABLE} where offer_id=%s",
        (row["offer_id"],),
    ).fetchone()
    assert str(updated[0]) == "94.30"
    assert str(updated[1]) == "0.00"
    assert updated[2] == newer
    assert (
        db.execute(
            f"select count(*) from {AUDIT} where offer_id=%s", (row["offer_id"],)
        ).fetchone()[0]
        == 2
    )


@pytest.mark.parametrize(
    "variant",
    [
        {"verified_at": lambda now: now - timedelta(hours=73), "decision": "verified"},
        {"verified_at": lambda now: now + timedelta(minutes=10), "decision": "verified"},
    ],
)
def test_sql_rejects_old_and_future_verification(db, variant):
    import psycopg

    row = observation()
    row["verified_at"] = variant["verified_at"](datetime.now(UTC))
    row["decision"] = variant["decision"]
    db.execute("set local role service_role")
    with pytest.raises(psycopg.errors.RaiseException), db.transaction():
        insert(db, row)


@pytest.mark.parametrize(
    "field,value",
    [
        ("product_id", "SC-WRONG"),
        ("merchant_product_id", "WRONG-SIZE"),
        ("merchant_id", "other-merchant"),
        ("identity_sha256", "e" * 64),
        ("currency", "USD"),
    ],
)
def test_sql_never_mutates_canonical_identity(db, field, value):
    import psycopg

    row = observation()
    db.execute("set local role service_role")
    insert(db, row)
    with (
        pytest.raises(psycopg.errors.RaiseException, match="canonical offer identity"),
        db.transaction(),
    ):
        db.execute(
            f"update {TABLE} set {field}=%s, verified_at=%s where offer_id=%s",
            (value, datetime.now(UTC) - timedelta(minutes=1), row["offer_id"]),
        )


def test_sql_hold_audited_and_monotone(db):
    import psycopg

    row = observation()
    db.execute("set local role service_role")
    insert(db, row)
    newer = row["verified_at"] + timedelta(minutes=5)
    db.execute(
        f"""update {TABLE}
        set decision='hold',price=null,shipping_cost=null,in_stock=null,verified_at=%s
        where offer_id=%s""",
        (newer, row["offer_id"]),
    )
    current = db.execute(
        f"select decision,price,shipping_cost,in_stock from {TABLE} where offer_id=%s",
        (row["offer_id"],),
    ).fetchone()
    assert current == ("hold", None, None, None)
    assert (
        db.execute(
            f"select count(*) from {AUDIT} where offer_id=%s", (row["offer_id"],)
        ).fetchone()[0]
        == 2
    )
    with (
        pytest.raises(psycopg.errors.RaiseException, match="must advance strictly"),
        db.transaction(),
    ):
        db.execute(
            f"update {TABLE} set price=50,verified_at=%s where offer_id=%s",
            (newer, row["offer_id"]),
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("price", None),
        ("shipping_cost", None),
        ("in_stock", None),
        ("in_stock", False),
    ],
)
def test_sql_verified_requires_known_total_and_real_stock(db, field, value):
    import psycopg

    row = observation("ci-incomplete-" + field + "-" + str(value))
    row[field] = value
    row["decision"] = "verified"
    db.execute("set local role service_role")
    with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
        insert(db, row)


def test_sql_accepts_evidence_backed_empty_hold_and_audits(db):
    row = observation("ci-nullable-hold-100")
    row.update(decision="hold", price=None, shipping_cost=None, in_stock=None)
    db.execute("set local role service_role")
    insert(db, row)
    assert db.execute(
        f"select decision,price,shipping_cost,in_stock from {TABLE} where offer_id=%s",
        (row["offer_id"],),
    ).fetchone() == ("hold", None, None, None)
    assert (
        db.execute(
            f"select count(*) from {AUDIT} where offer_id=%s", (row["offer_id"],)
        ).fetchone()[0]
        == 1
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [("price", "100.00"), ("shipping_cost", "0.00"), ("in_stock", False)],
)
def test_sql_hold_rejects_stale_price_or_asserted_stock(db, field, value):
    import psycopg

    row = observation("ci-unsafe-hold-" + field)
    row.update(decision="hold", price=None, shipping_cost=None, in_stock=None)
    row[field] = value
    db.execute("set local role service_role")
    with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
        insert(db, row)


@pytest.mark.parametrize("source_skew_minutes", [0, 4])
def test_sql_hold_is_immediate_without_retiming_or_replaying_positive_evidence(
    db, source_skew_minutes
):
    import psycopg

    # Same-second observations and accepted source clock skew must not prevent
    # an operator from withdrawing a purchase action at its actual observation time.
    hold_at = datetime.now(UTC)
    positive_at = hold_at + timedelta(minutes=source_skew_minutes)
    row = observation(f"ci-immediate-hold-{source_skew_minutes}")
    row["verified_at"] = positive_at
    db.execute("set local role service_role")
    insert(db, row)
    db.execute(
        f"""update {TABLE}
        set decision='hold',price=null,shipping_cost=null,in_stock=null,
            verified_at=%s,source_ref='ci-real-hold-observation',evidence_sha256=%s
        where offer_id=%s""",
        (hold_at, "c" * 64, row["offer_id"]),
    )
    assert db.execute(
        f"""select decision,price,shipping_cost,in_stock,verified_at,source_watermark_at
        from {TABLE} where offer_id=%s""",
        (row["offer_id"],),
    ).fetchone() == ("hold", None, None, None, hold_at, positive_at)
    assert db.execute(
        f"""select (prior_row->>'verified_at')::timestamptz,
                   (next_row->>'verified_at')::timestamptz,
                   (next_row->>'source_watermark_at')::timestamptz
        from {AUDIT} where offer_id=%s order by audit_id desc limit 1""",
        (row["offer_id"],),
    ).fetchone() == (positive_at, hold_at, positive_at)

    # A naive exception for HOLD must not lower the timestamp required for a
    # later positive quote. In the skew case these replays are newer than HOLD.
    for replay_at in (positive_at - timedelta(seconds=1), positive_at):
        with (
            pytest.raises(psycopg.errors.RaiseException, match="must advance strictly"),
            db.transaction(),
        ):
            db.execute(
                f"""update {TABLE}
                set decision='verified',price=90,shipping_cost=0,in_stock=true,
                    verified_at=%s,source_watermark_at=%s
                where offer_id=%s""",
                (replay_at, hold_at - timedelta(days=1), row["offer_id"]),
            )
    with (
        pytest.raises(psycopg.errors.RaiseException, match="must advance strictly"),
        db.transaction(),
    ):
        db.execute(
            f"update {TABLE} set verified_at=%s where offer_id=%s",
            (hold_at, row["offer_id"]),
        )
    assert db.execute(
        f"select decision from {TABLE} where offer_id=%s", (row["offer_id"],)
    ).fetchone() == ("hold",)

    # Genuinely later positive evidence can restore the existing canonical offer.
    newer = positive_at + timedelta(seconds=1)
    db.execute(
        f"""update {TABLE}
        set decision='verified',price=95,shipping_cost=0,in_stock=true,
            verified_at=%s,source_ref='ci-new-positive-observation',evidence_sha256=%s
        where offer_id=%s""",
        (newer, "d" * 64, row["offer_id"]),
    )
    assert db.execute(
        f"select decision,verified_at,source_watermark_at from {TABLE} where offer_id=%s",
        (row["offer_id"],),
    ).fetchone() == ("verified", newer, newer)
    assert db.execute(
        f"select count(*) from {AUDIT} where offer_id=%s", (row["offer_id"],)
    ).fetchone() == (3,)


@pytest.mark.parametrize("forged_year", [2000, 2099])
def test_sql_source_watermark_is_owned_by_trigger_on_insert_and_update(db, forged_year):
    row = observation(f"ci-watermark-forgery-{forged_year}")
    forged = datetime(forged_year, 1, 1, tzinfo=UTC)
    row["source_watermark_at"] = forged
    db.execute("set local role service_role")
    insert(db, row)
    assert db.execute(
        f"select source_watermark_at from {TABLE} where offer_id=%s", (row["offer_id"],)
    ).fetchone() == (row["verified_at"],)
    newer = row["verified_at"] + timedelta(minutes=1)
    db.execute(
        f"update {TABLE} set verified_at=%s,source_watermark_at=%s where offer_id=%s",
        (newer, forged, row["offer_id"]),
    )
    assert db.execute(
        f"select source_watermark_at from {TABLE} where offer_id=%s", (row["offer_id"],)
    ).fetchone() == (newer,)


@pytest.mark.parametrize(
    ("field", "value"),
    [("price", "100.00"), ("shipping_cost", "0.00"), ("in_stock", False)],
)
def test_sql_immediate_hold_still_rejects_commerce_claims(db, field, value):
    import psycopg

    row = observation("ci-immediate-unsafe-hold-" + field)
    omitted = ",".join(
        f"{name}=null" for name in ("price", "shipping_cost", "in_stock") if name != field
    )
    db.execute("set local role service_role")
    insert(db, row)
    with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
        db.execute(
            f"""update {TABLE}
            set decision='hold',{omitted},{field}=%s where offer_id=%s""",
            (value, row["offer_id"]),
        )


def test_sql_immediate_hold_still_cannot_change_canonical_identity(db):
    import psycopg

    row = observation("ci-immediate-hold-identity")
    db.execute("set local role service_role")
    insert(db, row)
    with (
        pytest.raises(psycopg.errors.RaiseException, match="canonical offer identity"),
        db.transaction(),
    ):
        db.execute(
            f"""update {TABLE}
            set decision='hold',price=null,shipping_cost=null,in_stock=null,
                merchant_product_id='WRONG-SIZE' where offer_id=%s""",
            (row["offer_id"],),
        )
