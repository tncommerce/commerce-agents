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
    db.execute(
        f"""insert into {TABLE}
        (offer_id,product_id,merchant_id,merchant_product_id,identity_sha256,
         currency,price,shipping_cost,in_stock,verified_at,decision,
         source_type,source_ref,evidence_sha256)
        values
        (%(offer_id)s,%(product_id)s,%(merchant_id)s,%(merchant_product_id)s,
         %(identity_sha256)s,%(currency)s,%(price)s,%(shipping_cost)s,
         %(in_stock)s,%(verified_at)s,%(decision)s,%(source_type)s,
         %(source_ref)s,%(evidence_sha256)s)""",
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
    assert db.execute(
        f"select count(*) from {AUDIT} where offer_id=%s", (row["offer_id"],)
    ).fetchone()[0] == 2


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
    with pytest.raises(psycopg.errors.RaiseException, match="canonical offer identity"), (
        db.transaction()
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
        f"update {TABLE} set decision='hold',verified_at=%s where offer_id=%s",
        (newer, row["offer_id"]),
    )
    assert db.execute(
        f"select decision from {TABLE} where offer_id=%s", (row["offer_id"],)
    ).fetchone()[0] == "hold"
    with pytest.raises(psycopg.errors.RaiseException, match="must advance strictly"), (
        db.transaction()
    ):
        db.execute(
            f"update {TABLE} set price=50,verified_at=%s where offer_id=%s",
            (newer, row["offer_id"]),
        )
