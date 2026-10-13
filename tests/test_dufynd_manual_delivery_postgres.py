"""Real PostgreSQL, disposable database; never uses the production project."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest

DSN = os.getenv("DUFYND_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="dedicated PostgreSQL service required")
ROOT = Path(__file__).resolve().parents[1]
HASH = "a" * 64


def bootstrap(c):
    c.execute("""
      create table public.dufynd_content_assets(id text primary key,metadata jsonb default '{}');
      create table public.dufynd_human_decisions(decision_id text primary key);
      create table public.dufynd_master_status(key text primary key,category text not null,
        value jsonb not null,updated_at timestamptz default now());
      do $$ begin
       if not exists(select 1 from pg_roles where rolname='anon') then create role anon; end if;
       if not exists(select 1 from pg_roles where rolname='authenticated') then create role authenticated; end if;
       if not exists(select 1 from pg_roles where rolname='service_role') then create role service_role; end if;
      end $$;
    """)
    c.execute(
        (ROOT / "supabase/migrations/20261009000416_dufynd_publish_dispatch.sql")
        .read_text()
        .split("create function public.read_dufynd_publish_packet_v1")[0]
    )
    c.execute(
        "insert into dufynd_content_assets(id) values('asset'); insert into dufynd_human_decisions values('decision');"
    )


def reserve(c, content="creative", digest=HASH):
    return c.execute(
        """insert into dufynd_publish_dispatches(asset_id,revision_fingerprint,
      asset_sha256,content_id,platform,brand_id,owner_decision_id)
      values('asset','fixture',%s,%s,'instagram','7182186','decision') returning dispatch_id""",
        (digest, content),
    ).fetchone()[0]


def manual(c, state="MANUAL_PUBLISHED", content="creative", digest=HASH):
    return c.execute(
        "select record_dufynd_manual_delivery_v1(%s,'instagram',%s,%s,'123','-456','fixture:readback')",
        (content, digest, state),
    ).fetchone()[0]


@pytest.fixture(scope="module")
def isolated_dsn():
    import psycopg
    from psycopg.conninfo import make_conninfo
    from psycopg.sql import SQL, Identifier

    name = "operations06_" + uuid4().hex
    with psycopg.connect(DSN, autocommit=True) as admin:
        admin.execute(SQL("create database {}").format(Identifier(name)))
    url = make_conninfo(DSN, dbname=name)
    try:
        with psycopg.connect(url, autocommit=True) as c:
            bootstrap(c)
            # Reproduce on the unmodified real dispatch DDL before installing fix.
            c.execute(
                "insert into dufynd_master_status(key,category,value) values('content.manual_delivery:7182186:instagram:creative','content',%s::jsonb)",
                (
                    json.dumps(
                        {
                            "content_id": "creative",
                            "platform": "instagram",
                            "asset_sha256": HASH,
                            "state": "MANUAL_PUBLISHED",
                        }
                    ),
                ),
            )
            assert reserve(c)  # BUG: pre-fix reservation ignores manual publication.
            c.execute("truncate dufynd_master_status,dufynd_publish_dispatches")
            c.execute((ROOT / "docs/sql/dufynd_manual_publication_guard.sql").read_text())
        yield url
    finally:
        with psycopg.connect(DSN, autocommit=True) as admin:
            admin.execute(SQL("drop database {} with (force)").format(Identifier(name)))


@pytest.fixture
def db(isolated_dsn):
    import psycopg

    with psycopg.connect(isolated_dsn, autocommit=True) as c:
        c.execute("truncate dufynd_master_status,dufynd_publish_dispatches")
        c.execute("update dufynd_content_assets set metadata='{}'")
        yield c


@pytest.mark.parametrize("state", ["MANUAL_PENDING", "MANUAL_PUBLISHED", "MANUAL_UNKNOWN"])
def test_manual_states_block_relabelled_hash_and_content(db, state):
    import psycopg

    assert manual(db, state)["auto_publish_allowed"] is False
    for content, digest in [("creative", HASH), ("alias", HASH), ("creative", "b" * 64)]:
        with pytest.raises(psycopg.errors.RaiseException, match="manual_delivery_blocks"):
            reserve(db, content, digest)


def test_terminal_idempotency_and_identity_conflicts(db):
    import psycopg

    manual(db)
    assert manual(db, "MANUAL_PENDING")["state"] == "MANUAL_PUBLISHED"
    assert db.execute("select count(*) from dufynd_master_status").fetchone()[0] == 1
    for content, digest in [("alias", HASH), ("creative", "b" * 64)]:
        with pytest.raises(psycopg.errors.RaiseException):
            manual(db, content=content, digest=digest)


def test_manual_receipt_after_reservation_fences_delayed_claim(db):
    import psycopg

    did = reserve(db)
    assert manual(db)["existing_dispatch_requires_reconciliation"] is True
    with pytest.raises(psycopg.errors.RaiseException, match="manual_delivery_blocks"):
        db.execute(
            "update dufynd_publish_dispatches set receipt='{\"invocation_claimed\":true}' where dispatch_id=%s",
            (did,),
        )
    # Actual late provider truth is still recordable; never erase the old dispatch.
    db.execute(
        "update dufynd_publish_dispatches set state='outcome_unknown',receipt='{\"reason\":\"reconcile\"}' where dispatch_id=%s",
        (did,),
    )
    assert db.execute("select count(*) from dufynd_publish_dispatches").fetchone()[0] == 1


def test_canonical_release_identity_and_corrupt_state_remain_blocked(db):
    import psycopg

    manual(db)
    db.execute('update dufynd_content_assets set metadata=\'{"release_content_id":"creative"}\'')
    db.execute("update dufynd_master_status set value=value || '{\"state\":null}'")
    with pytest.raises(psycopg.errors.RaiseException, match="manual_delivery_blocks"):
        reserve(db, "creative:instagram:v2", "b" * 64)


def test_concurrent_manual_commit_blocks_waiting_reservation_and_survives_reconnect(
    db, isolated_dsn
):
    import psycopg

    started = Event()

    def delayed():
        with psycopg.connect(isolated_dsn, autocommit=True) as c:
            started.set()
            with pytest.raises(psycopg.errors.RaiseException, match="manual_delivery_blocks"):
                reserve(c)

    with ThreadPoolExecutor(max_workers=1) as pool:
        with psycopg.connect(isolated_dsn) as first:
            manual(first)
            pending = pool.submit(delayed)
            assert started.wait(3)
            assert not pending.done()
        pending.result(timeout=5)
    with (
        psycopg.connect(isolated_dsn, autocommit=True) as restarted,
        pytest.raises(psycopg.errors.RaiseException, match="manual_delivery_blocks"),
    ):
        reserve(restarted)


def test_failed_manual_transaction_leaves_no_false_receipt(db, isolated_dsn):
    import psycopg

    with psycopg.connect(isolated_dsn) as failed:
        manual(failed)
        failed.rollback()
    assert db.execute("select count(*) from dufynd_master_status").fetchone()[0] == 0
    assert reserve(db)


def test_manual_platform_does_not_block_unrelated_platform(db):
    manual(db)
    result = db.execute(
        """insert into dufynd_publish_dispatches(asset_id,revision_fingerprint,
      asset_sha256,content_id,platform,brand_id,owner_decision_id)
      values('asset','fixture',%s,'creative','tiktok','7182186','decision') returning dispatch_id""",
        (HASH,),
    ).fetchone()[0]
    assert result


def test_manual_after_claim_reports_conflict_without_false_cancellation(db):
    did = reserve(db)
    db.execute(
        "update dufynd_publish_dispatches set receipt='{\"invocation_claimed\":true}' where dispatch_id=%s",
        (did,),
    )
    assert manual(db)["existing_dispatch_requires_reconciliation"] is True
    assert (
        db.execute("select receipt from dufynd_publish_dispatches").fetchone()[0][
            "invocation_claimed"
        ]
        is True
    )


def test_no_new_public_rpc_permissions(db):
    for role in ["anon", "authenticated"]:
        assert (
            db.execute(
                "select has_function_privilege(%s,'public.record_dufynd_manual_delivery_v1(text,text,text,text,text,text,text)','execute')",
                (role,),
            ).fetchone()[0]
            is False
        )
