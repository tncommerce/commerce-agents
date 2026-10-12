# Bounded zero-cost nightshift — development draft

This runner performs scheduled **offline deterministic checks**, not autonomous
creative/model work. It has no provider, HTTP, database-service, browser, GitHub
write, publication, shell-task or credential adapter. The existing paid counted
Nightshift and seven-worker production contracts are unchanged.

## Concrete implementation

`python -m scripts.dufynd_zero_cost_nightshift` accepts a bounded dated JSON plan
and a private SQLite state path. It waits until the actual timezone-aware due
time while its process is alive, claims due tasks transactionally, and continues
past individual OWNER_HOLDs. No cron, service or workflow is installed by the CLI.

- Repository identity is exactly `tncommerce/commerce-agents`; only `dufynd-*`
  development branches run. Main, production and detached checkouts are rejected.
- Pin the exact checkout commit, runner SHA256 and each input's SHA256. Changed
  checkout/code/input stops or holds before execution. Only bounded local JSON
  in docs/config/retail-data is readable; paths escaping the repo and symlinks
  are rejected. Reports contain fixed statuses/counts, not input contents.
- The global completed-work key includes action, runner digest and exact inputs;
  a later plan/date/unrelated checkout commit does not repeat identical work.
- SQLite `BEGIN IMMEDIATE` serializes claims across processes and plans. A
  30-second lease/token fences late workers. Result and completion commit in one
  transaction. A process crash leaves a durable claim; at most two attempts per
  task allow resuming **pure, repeatable local checks** after expiry. This is
  at-least-once computation with a deduplicated committed result, not a claim of
  exactly-once external effects. No external-effect adapter exists.
- Plans contain at most 100 tasks, ten inputs per task, 1 MB per file, an eight-
  hour dated window, forty total attempts and ten tasks per invocation. Default
  process duration is 60 seconds, hard configuration cap 900 seconds; monotonic
  time bounds waiting even if wall-clock time moves backward. Local parsing and
  SQLite lock/IO completion are not hard real-time deadlines; the optional host
  service adds an independent runtime cap.
- Dependency cycles/unknown IDs fail closed. Blocked dependencies become holds;
  other due tasks continue. Explicit STOP file, expired window, changed plan,
  changed checkout/runner and exhausted attempts prevent additional work.
- Reusing a plan ID with changed contents fails. Resume the same plan and DB;
  reviewed new inputs require a new plan ID. Retain the DB across process/host
  restarts. Normal startup requires existing versioned state and never creates
  or repairs a missing/empty/invalid DB. A storage incident is a STOP; restore
  the preserved state before resuming. Do not initialize a replacement and call
  that successful resume. Initialization is explicit and refuses existing files.

## Disabled example and authorized local validation

`config/dufynd_zero_cost_nightshift.example.json` is **disabled**, expired after
its specific dated window, and initially pins the RC1 base. It is not a recurring
approval or an installed scheduler. Its source packet was recovered unchanged
from PR #774's prior manufacturer research, avoiding repeated source fetches.

For a local development trial, copy the plan outside git, assign a new plan ID,
pin the current development commit/runner/input hashes, set a short current dated
window and due times, and set enabled=true in that private copy. Run:

```sh
python -m scripts.dufynd_zero_cost_nightshift \
  --plan /existing-private-state/plan.json \
  --state /existing-private-state/queue.sqlite --initialize-state \
  --root /existing-dufynd-development-checkout --max-seconds 60 \
  --stop-file /existing-private-state/STOP
```

Use `--initialize-state` only for this first new-state trial. Omit it for every
resume and scheduled invocation; it fails if the file already exists. The
service template intentionally has no initialization flag. Earlier development
smoke databases without the state-version marker fail closed; they are not
silently migrated or erased. Restore valid state after loss, or explicitly
review a new isolated trial with no continuity claim.

No account, model, merchant or analytics calls occur. `source_intake` checks
structure and disallowed claims only. It explicitly does **not** certify source
truth, GTIN, rights, offer readiness or release approval. The three candidate
records remain unstaged and unpublished.

## Real external timing proposal — NOT ACTIVATED

The `.service.example` and `.timer.example` files under this directory are inert
review artifacts. A future approved existing no-additional-cost Linux host may
invoke one bounded tick every five minutes during Berlin night hours. It needs
an existing dedicated unprivileged account, development checkout, Python/Git,
and private durable local state. PrivateNetwork and read-only checkout prevent
provider/network access; only the state directory is writable. No credentials
are needed. Do not add Render resources, paid runners, DB migrations, rights,
users or storage from this draft. Do not add a default-branch GitHub cron.

OWNER_HOLD for activation: approve the exact host, verified zero incremental
cost, service account/paths, dated plan, state durability and both unit files.
No unit is installed/enabled/started here. Unit templates require validation on
that host; they are not certified for an unavailable host. ChatGPT Work sessions
cannot be kept alive or restarted by this script; a timer needs an independently
authorized runtime. A clock-aware local process is implemented and tested; an
always-on production runtime is deliberately absent.

## Evidence / continuation

Regression suite: `tests/test_dufynd_zero_cost_nightshift.py`. Covers actual
wall-clock due time, real process death, competing SQLite connections, durable
attempt limits, stale leases, deduplication, unchanged and changed input,
checkout/runner gates, dependency holds/cycles, STOP and disabled/window/runtime
limits; missing, empty, corrupt or incomplete resume state is refused without
repair, and initialization cannot overwrite history. Network is denied in the
offline handler regression.

The local smoke below uses only a short private plan and existing source facts;
never mark a production timer active based on a test passing. CI and final smoke
results are recorded in this draft PR description without rerunning older PRs.
