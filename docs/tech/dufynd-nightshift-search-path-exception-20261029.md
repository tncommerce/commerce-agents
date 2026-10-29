# Nightshift procedure search-path exception — 2026-10-29

## Decision and exact scope

Retain the existing private, transaction-controlling procedures. Their mutable
`search_path` remains a documented exception: attaching a procedure-level `SET`
breaks both normal execution and the abort path at the first `COMMIT`. No SQL
migration, privilege change, activation or production execution was performed.
The advisor finding has not been claimed as resolved.

This review used production project `bqsdxaagklpkxioaqdqa` read-only and repository
base `42b6aef79f612b0c45af33e2e33db70286bb4598` (tree
`dd701757330d96b0b0c1b06b6dad8cd476283887`). The final catalog snapshot was
**2026-10-29 14:23:24.882 UTC**. Both objects are PL/pgSQL **procedures**
(`prokind=p`), owned by `postgres`, `SECURITY INVOKER`, with `proconfig=NULL`
and ACL `{postgres=X/postgres}`. Effective `EXECUTE` is false for each of
`anon`, `authenticated` and `service_role`.

| Exact signature in `public` | `md5(prosrc)` | `md5(pg_get_functiondef(oid))` |
| --- | --- | --- |
| `dufynd_ns_v1_cycle()` | `fadf1d018b8867af982e95c526466af9` | `cc158747c58b5a3282da8de8d39859fe` |
| `dufynd_ns_v1_pilot_abort()` | `358b9793d9d69d59a997307610c5b344` | `f9da986d0b8ae6bd9c4a901613d02a70` |

## Exposure and caller boundaries

All application-helper calls in the two bodies explicitly name `public`.
Their Nightshift helpers (`pilot_poll`, `pilot_restore`, `claim`, `finish`,
`pilot_arm` and `code_hash`) are also postgres-owned invoker functions, have
`search_path=public` and grant `EXECUTE` only to `postgres`. The separately
callable CEO function grants `service_role` execution but does not grant that
role permission to execute either procedure. None of `anon`, `authenticated`
or `service_role` has `CREATE` in `public`.

The inspected cron catalog has no current command referencing either procedure
and no Nightshift-named job. The current config is `enabled=false`, `stop=true`;
the recorded pilot is `restored` with `stop_reason=window_closed`. Those stored
records were last verified on 2026-10-13 at 20:50:00 UTC. The catalog body search
found the cycle command in the private pilot arm/poll/restore functions; it
found no caller of `pilot_abort`. This is evidence about inspected database
code and current cron configuration, not a proof about every external or
dynamically constructed administrative call.

`pilot_arm(text)` requires a serializable transaction, an exact approved
manifest, the current code hash and its fixed cron baseline before installing
the literal `CALL public.dufynd_ns_v1_cycle();`. Its code-hash helper aggregates
`pg_get_functiondef` for the Nightshift routines. An attached `SET` also changes
that definition and therefore the manifest's code-hash input. No manifest or
approval record was rewritten.

The direct application-role exposure is constrained by these verified private
ACLs and caller boundaries. Trusted administrative session context remains a
dependency. Reassess the exception if ownership, grants, schema-creation rights,
callers, routine bodies or pilot activation change; do not generalize it to
ordinary functions or publicly executable procedures.

## Native PostgreSQL evidence

Eight scenarios passed on PostgreSQL **17.11**, in the dedicated local database
`dufynd_nightshift_searchpath_tests` over Unix socket
`/tmp/dufynd-pg17-20261029/observer-socket`, port `55439`.
The exact live procedure bodies were installed and their source MD5s asserted.
Only their dependencies were replaced with local stage-logging stubs; those
stubs did not run business actions, cron changes or HTTP requests.

| Case | Observed result |
| --- | --- |
| Cycle, unarmed | `poll → restore → ceo` |
| Cycle, armed and claimed | `poll → ceo → claim → finish` |
| Cycle, armed and idle | `poll → ceo → claim` |
| Abort | `poll → restore`, abort flag true |
| Cycle after `ALTER PROCEDURE … SET search_path TO pg_catalog,public` | **SQLSTATE `2D000`: `invalid transaction termination`** |
| Abort after the same attached setting | **SQLSTATE `2D000`: `invalid transaction termination`** |
| Cycle after resetting the local setting | Original execution restored |
| Abort after resetting the local setting | Original execution restored |

Each baseline call was a single top-level autocommit `CALL`. The test verified
distinct transaction IDs between stages and serializable isolation in restore.
Both failing calls left no stage writes committed. Resetting the local setting
restored the exact original definition hashes. Result: **8 passed; 0 network
attempts recorded**. This proves the metadata-change incompatibility and the
tested transaction boundaries; it is not an end-to-end Nightshift business test.

PostgreSQL documents the restriction explicitly: a procedure with an attached
`SET` clause cannot execute transaction-control statements. See
[CREATE PROCEDURE, PostgreSQL 17](https://www.postgresql.org/docs/17/sql-createprocedure.html)
and [PL/pgSQL transaction management](https://www.postgresql.org/docs/17/plpgsql-transactions.html).
Moving settings into the body or introducing wrappers would require a separate
transaction/session-context design and new manifest-bound verification; it is
not an equivalent metadata-only fix.

## Reproduction artifacts

The original completed run is recorded at
`/tmp/dufynd-nightshift-searchpath-proof-20261029.log`. Its SHA-256 is
`35b4f2051f4dfaab0b85fba9c3372db813a582c21d7c3ec1ed1dd500dc578cd3`.
The test was not repeated after this report was assembled.

| Saved artifact under `/tmp` | SHA-256 |
| --- | --- |
| `dufynd-nightshift-searchpath-proof-20261029.py` | `d7f79c7f1dc36052287ace4ac02a68bf55fa28339a944e96b3c25e61a7ad1280` |
| `dufynd_ns_v1_cycle_live_20261029.sql` | `cf25e9c4219e17f6ad886ff4a1ed39bfe36a8186e1bdf0f05e9db8385775de29` |
| `dufynd_ns_v1_pilot_abort_live_20261029.sql` | `3b01bd2e1091ee6fafcf3584b610a7497320dffe1a7f4b25ac89217368e8b651` |

The appendices preserve these three source files verbatim for reproduction in
a disposable local cluster. Save each block under its stated `/tmp` filename;
the test uses the fixed local socket and dedicated database above. It creates
local stub functions and alters only these local copies. With that local
cluster already running and `psycopg` available, the original command is:

```sh
/workspace/scratch/9dc0a38d18d8/dufynd-followup-venv/bin/python /tmp/dufynd-nightshift-searchpath-proof-20261029.py
```

<details>
<summary>dufynd_ns_v1_cycle_live_20261029.sql</summary>

```sql
CREATE OR REPLACE PROCEDURE public.dufynd_ns_v1_cycle()
 LANGUAGE plpgsql
AS $procedure$
declare c jsonb; armed boolean;
begin
 armed:=public.dufynd_ns_v1_pilot_poll();
 commit;
 -- Must precede even PL/pgSQL IF expression evaluation in the new transaction.
 set transaction isolation level serializable;
 if not armed then
  begin
   perform public.dufynd_ns_v1_pilot_restore();
  exception when serialization_failure then
   raise log 'nightshift restore serialization conflict; retry on existing tick';
  end;
 end if;
 commit;
 perform public.run_dufynd_ceo_with_missions_v1();
 commit;
 if not armed then return; end if;
 c:=public.dufynd_ns_v1_claim();
 commit;
 if c->>'state'='claimed' then
  perform public.dufynd_ns_v1_finish(c->>'mission_key',c->>'task_id',(c->>'token')::uuid);
  commit;
 end if;
end $procedure$
```

</details>

<details>
<summary>dufynd_ns_v1_pilot_abort_live_20261029.sql</summary>

```sql
CREATE OR REPLACE PROCEDURE public.dufynd_ns_v1_pilot_abort()
 LANGUAGE plpgsql
AS $procedure$
begin
 perform public.dufynd_ns_v1_pilot_poll(true);
 commit;
 set transaction isolation level serializable;
 begin
  perform public.dufynd_ns_v1_pilot_restore();
 exception when serialization_failure then
  raise log 'nightshift restore serialization conflict; retry on existing tick';
 end;
 commit;
end $procedure$
```

</details>

<details>
<summary>dufynd-nightshift-searchpath-proof-20261029.py</summary>

```python
"""Isolated transaction-control proof for the exact two live Nightshift procedures."""

from pathlib import Path
import json
import socket

import psycopg

DATABASE = 'dufynd_nightshift_searchpath_tests'
ADMIN = 'postgresql://postgres@/postgres?host=/tmp/dufynd-pg17-20261029/observer-socket&port=55439'
with psycopg.connect(ADMIN, autocommit=True) as c:
    if not c.execute('select 1 from pg_database where datname=%s', (DATABASE,)).fetchone():
        c.execute('create database dufynd_nightshift_searchpath_tests')

attempts = []
original_socket = socket.socket


class LocalSocketOnly(original_socket):
    def connect(self, address):
        if self.family in (socket.AF_INET, socket.AF_INET6):
            attempts.append('tcp')
            raise AssertionError('No network traffic allowed')
        return super().connect(address)


def blocked_dns(*args, **kwargs):
    attempts.append('dns')
    raise AssertionError('No DNS allowed')


socket.socket = LocalSocketOnly
socket.create_connection = blocked_dns
socket.getaddrinfo = blocked_dns

source_hashes = {
    'dufynd_ns_v1_cycle': 'fadf1d018b8867af982e95c526466af9',
    'dufynd_ns_v1_pilot_abort': '358b9793d9d69d59a997307610c5b344',
}
results = []
with psycopg.connect(ADMIN.replace('/postgres?', '/' + DATABASE + '?'), autocommit=True) as c:
    assert c.execute('select current_database()').fetchone()[0] == DATABASE
    c.execute('''
      create table if not exists public.nightshift_test_config(armed boolean,claim_state text);
      create table if not exists public.nightshift_test_trace(
        id bigserial primary key,stage text,xid text,isolation text,abort_requested boolean);
      create or replace function public.dufynd_ns_v1_pilot_poll(p_abort boolean default false)
      returns boolean language plpgsql set search_path to public as $$ begin
        insert into public.nightshift_test_trace(stage,xid,isolation,abort_requested)
        values('poll',pg_current_xact_id()::text,current_setting('transaction_isolation'),p_abort);
        return (select armed from public.nightshift_test_config) and not p_abort;
      end $$;
      create or replace function public.dufynd_ns_v1_pilot_restore()
      returns jsonb language plpgsql set search_path to public as $$ begin
        if current_setting('transaction_isolation')<>'serializable' then
          raise exception 'serializable_restore_required';
        end if;
        insert into public.nightshift_test_trace(stage,xid,isolation)
        values('restore',pg_current_xact_id()::text,current_setting('transaction_isolation'));
        return '{}';
      end $$;
      create or replace function public.run_dufynd_ceo_with_missions_v1()
      returns jsonb language plpgsql set search_path to public as $$ begin
        insert into public.nightshift_test_trace(stage,xid,isolation)
        values('ceo',pg_current_xact_id()::text,current_setting('transaction_isolation'));
        return '{}';
      end $$;
      create or replace function public.dufynd_ns_v1_claim()
      returns jsonb language plpgsql set search_path to public as $$ begin
        insert into public.nightshift_test_trace(stage,xid,isolation)
        values('claim',pg_current_xact_id()::text,current_setting('transaction_isolation'));
        return jsonb_build_object('state',(select claim_state from public.nightshift_test_config),
          'mission_key','local-fixture','task_id','local-fixture',
          'token','11111111-1111-4111-8111-111111111111');
      end $$;
      create or replace function public.dufynd_ns_v1_finish(text,text,uuid)
      returns jsonb language plpgsql set search_path to public as $$ begin
        insert into public.nightshift_test_trace(stage,xid,isolation)
        values('finish',pg_current_xact_id()::text,current_setting('transaction_isolation'));
        return '{}';
      end $$;
    ''')
    originals = {}
    for name, expected in source_hashes.items():
        c.execute(Path('/tmp/' + name + '_live_20261029.sql').read_text())
        c.execute('revoke all on procedure public.' + name + '() from public')
        actual, config, security = c.execute(
            'select md5(prosrc),proconfig,prosecdef from pg_proc where oid=%s::regprocedure',
            ('public.' + name + '()',),
        ).fetchone()
        assert (actual, config, security) == (expected, None, False)
        originals[name] = c.execute(
            'select md5(pg_get_functiondef(%s::regprocedure))', ('public.' + name + '()',)
        ).fetchone()[0]

    def configure(armed, claim_state='claimed'):
        c.execute('truncate public.nightshift_test_trace')
        c.execute('delete from public.nightshift_test_config')
        c.execute('insert into public.nightshift_test_config values(%s,%s)', (armed, claim_state))

    def run(name, armed, expected, claim_state='claimed'):
        configure(armed, claim_state)
        # One top-level autocommit CALL: an explicit surrounding transaction
        # would itself prohibit COMMIT and invalidate this reproduction.
        c.execute('call public.' + name + '()')
        rows = c.execute(
            'select stage,xid,isolation,abort_requested from public.nightshift_test_trace order by id'
        ).fetchall()
        assert [row[0] for row in rows] == expected, rows
        assert len({row[1] for row in rows}) == len(rows), rows
        assert all(row[2]=='serializable' for row in rows if row[0]=='restore')
        assert rows[0][3] is (name == 'dufynd_ns_v1_pilot_abort')
        results.append({'case': name, 'armed': armed, 'claim': claim_state,
                        'result': 'baseline_or_restored_ok', 'stages': expected})

    run('dufynd_ns_v1_cycle', False, ['poll','restore','ceo'])
    run('dufynd_ns_v1_cycle', True, ['poll','ceo','claim','finish'])
    run('dufynd_ns_v1_cycle', True, ['poll','ceo','claim'], 'idle')
    run('dufynd_ns_v1_pilot_abort', True, ['poll','restore'])

    for name in source_hashes:
        c.execute('alter procedure public.' + name + '() set search_path to pg_catalog,public')
        assert c.execute(
            'select md5(pg_get_functiondef(%s::regprocedure))', ('public.' + name + '()',)
        ).fetchone()[0] != originals[name]
        configure(True)
        try:
            c.execute('call public.' + name + '()')
        except psycopg.Error as error:
            assert error.sqlstate == '2D000', (name, error.sqlstate)
            assert 'invalid transaction termination' in str(error)
            assert c.execute('select count(*) from public.nightshift_test_trace').fetchone()[0] == 0
            results.append({'case': name, 'attached_search_path': True,
                            'result': 'reproduced_failure', 'sqlstate': error.sqlstate})
        else:
            raise AssertionError('Attached SET unexpectedly preserved transaction control: ' + name)
        finally:
            c.execute('alter procedure public.' + name + '() reset search_path')
        assert c.execute(
            'select md5(pg_get_functiondef(%s::regprocedure))', ('public.' + name + '()',)
        ).fetchone()[0] == originals[name]

    run('dufynd_ns_v1_cycle', True, ['poll','ceo','claim','finish'])
    run('dufynd_ns_v1_pilot_abort', True, ['poll','restore'])

print(json.dumps({'postgres': '17.11', 'database': DATABASE, 'cases': results,
                  'passed': len(results), 'network_attempts': len(attempts)}, indent=2))
assert len(results) == 8 and not attempts
```

</details>
