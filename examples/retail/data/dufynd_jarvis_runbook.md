# DUFYND Jarvis Operating Runbook

Status: active_internal
Brand: DUFYND
Operator: TNCommerce

## Purpose

Jarvis is the internal DUFYND operating and learning agent. It is not the
customer-facing fragrance advisor.

Jarvis should use the Supabase DUFYND knowledge base as its durable operating
context instead of relying on chat history or static memory alone.

## Startup context

Before planning a DUFYND business, content, affiliate, launch or creative task,
load the current internal context with:

```powershell
python scripts/dufynd_jarvis_bridge.py context --machine-readable
```

For creative work:

```powershell
python scripts/dufynd_jarvis_bridge.py creative-context --machine-readable
```

For autonomous work planning:

```powershell
python scripts/dufynd_jarvis_bridge.py autonomy --machine-readable
```

For controlled creative scoring:

```powershell
python scripts/dufynd_jarvis_bridge.py experiment-rubric --machine-readable
```

For launch-specific work:

```powershell
python scripts/dufynd_jarvis_bridge.py refresh-launch-gate --machine-readable
```

The comprehensive context contains:
- current master/business status
- approved creative references
- reusable creative patterns
- reference-to-pattern and idea-to-pattern learning
- repeatable content formats
- hook templates
- content ideas
- durable lessons
- experiment scoring rubric
- autonomous-task queue
- approval boundaries
- affiliate partner state
- recent AI-video experiments
- model/format learning aggregates
- content funnel outcomes
- launch and R&D gate state


## Passive and active runtime

Jarvis has two operating layers.

Passive capture is safe to leave on continuously:
- new creative references are queued
- new AI-video experiments are queued
- new content-performance rows are queued
- affiliate partner status changes are queued
- resolved human decisions are queued
- no model call is made and no model cost is incurred

Inspect the current internal health state with:

```powershell
python scripts/dufynd_jarvis_bridge.py health --machine-readable
```

Check whether the active runner is configured without invoking a model:

```powershell
python scripts/dufynd_jarvis_runtime.py --readiness
```

Active model execution is disabled by default. It requires:
- explicit operator approval
- `DUFYND_JARVIS_ACTIVE=1`
- an explicit `DUFYND_JARVIS_MODEL`
- an active `DUFYND_JARVIS_BUDGET_ID`
- Anthropic credentials
- Supabase service-role credentials

The runner supports two guarded active modes. `--process-next` processes one
inbox event. `--process-loop` is the bounded supervisor mode: one explicit
operator activation may process several queued events sequentially without a new
approval between events. The loop defaults to eight events and hard-clamps the
requested limit to twenty. It stops when the inbox is empty, the event limit is
reached, an event fails, or the active runtime/budget window refuses another run.

Each event still has the same model guardrails. The default maximum is eight agent
turns and the runtime clamps the configured value to twelve. Active runs also have
a per-event USD budget guard: the default is $0.25 via
`DUFYND_JARVIS_MAX_BUDGET_USD`, and the runtime clamps any configured value to a
hard maximum of $1.00 per event run. The database budget window remains the
authoritative aggregate spend/run cap, so supervisor mode cannot bypass financial
limits by chaining events.

The first activation window is `jarvis_activation_pilot_001`. A model run is
refused whenever that window does not permit another run, even if credentials and
`DUFYND_JARVIS_ACTIVE=1` are present.

A guarded GitHub Actions workflow exists at
`.github/workflows/dufynd-jarvis-manual.yml`. Its default mode is readiness-only.
Both `process-next` and `process-loop` refuse active processing unless the
operator deliberately supplies the `GO-JARVIS-ACTIVE` approval token. Supervisor
mode therefore replaces repeated per-event confirmations with one bounded-session
approval without expanding Jarvis's tool permissions.

## Control-plane state sync

The repository-derived Jarvis master status is the operational source of truth for
current work selection. Supabase remains the durable memory, audit and event store.

Before active Jarvis processing, the runner should:

1. rebuild the derived repository state with `refresh_scentai_jarvis_state.py --write`
2. mirror the canonical master snapshot and current domain tasks with
   `sync_dufynd_repo_state_to_supabase.py --write`
3. verify exact `source_fingerprint_sha256` parity with
   `dufynd_jarvis_freshness.py`
4. refuse autonomy-queue work when the fingerprint or canonical snapshot is stale

The sync is intentionally narrow. It upserts
`jarvis.repo_state_snapshot`, `repo_current_commerce` and
`repo_current_content`; it does not delete historical Jarvis records and does not
modify the live catalog, affiliate routing, public content or spend.

The GitHub Actions runner exposes a no-model `sync-state` mode for refreshing this
control plane without consuming Jarvis model budget. Both `process-next` and
`process-loop` perform the same refresh/sync/freshness sequence before active
model execution.

## Autonomous cycle

The guarded `--autonomous-cycle` mode is the bridge from manual Jarvis runs to
future unattended operation. It does not create a new spending authority.

Before the cycle can run:

1. repository-derived Jarvis state is refreshed and synchronized to Supabase
2. the freshness guard must pass with exact fingerprint parity
3. `DUFYND_JARVIS_ACTIVE=1` must be set
4. `DUFYND_JARVIS_AUTONOMOUS=1` must be set
5. the configured database budget window must still report `can_run=true`

A cycle processes at most two inbox events by default (hard maximum five). If an
inbox backlog remains, Jarvis defers repo-current work. Once the inbox is clear,
the cycle loads the current safe repo-derived task and routes it deterministically:
engineering work goes to the isolated branch worker; commerce, content, research
and other non-engineering safe work go to the read-only safe worker.

When the autonomous cycle invokes the branch worker, the workflow applies the same
path allowlist, Python checks and storefront web/visual QA used by explicit
`process-branch-task` runs. The resulting patch remains local to the workflow and
may be uploaded as an artifact; autonomous-cycle still has no push, merge, deploy,
publish or live-catalog mutation authority.

The autonomous switch is deliberately separate from the database budget window:
the switch authorizes unattended execution behavior, while the budget window is
the authoritative financial cap. Jarvis cannot create, enlarge, reactivate or
bypass that budget. No recurring schedule is enabled yet; scheduling is a separate
operator-controlled activation step.

## Nightshift Orchestrator v1

Nightshift is task-driven, not time-driven. One explicit pilot dispatch authorizes a
bounded session; Jarvis must stop when there is no safe useful work, a budget gate
closes, an external/human dependency blocks the next action, or a quality gate
requires review. It must not poll the model merely to stay active.

The existing control plane remains authoritative:

- repo state is refreshed and synchronized before the session
- exact fingerprint freshness is required
- `dufynd_autonomy_tasks` supplies persistent work state
- `dufynd_agent_runs` supplies the paid-run audit trail
- `jarvis.nightshift_session` stores session id, heartbeat, current task, outcomes
  and stop reason
- the active database budget window is checked before every paid worker attempt
- stable task state is preserved while the repo fingerprint is unchanged, avoiding
  duplicate work after a restart

Action classes are fail-closed:

- **GREEN / auto execute:** internal reads, research, analysis, reports, content
  preparation, isolated code preparation, tests, QA, evidence and task-state work
- **YELLOW / prepare only:** production-relevant PRs, live-catalog changes, new
  affiliate activation, publish-ready content, recommendation-logic changes and
  important external messages
- **RED / owner only:** spend, credits/subscriptions, budget increases, contracts,
  credentials/secrets, external commitments, live social publishing, irreversible
  production data changes, production merges and gate bypasses

The Nightshift worker router sends engineering work to the isolated branch worker
and non-engineering safe work to the read-only research worker. One engineering
patch may be prepared per checkout; non-engineering GREEN work can continue while
that patch waits for deterministic validation. Worker failures receive one bounded
retry by default, with the budget checked again before the retry. A final failure
marks that task blocked and allows Jarvis to choose another safe task instead of
aborting the entire session.

A successful engineering patch is validated by the existing path allowlist,
Python checks and, when storefront files changed, web build plus responsive visual
QA. The deterministic post-model handoff may create a `jarvis/worker-*` branch
and a PR against `scentai-mvp`, but it must never auto-merge and must never target
`main`. The task is then presented as READY FOR TUAN APPROVAL.

Every pilot ends with a machine-readable JSON report and a concise Markdown Morning
Report built from real persisted session state, queue state, health, pending
decisions, budget status and audited agent runs. No recurring Nightshift schedule
is enabled by v1.

## Autonomy control plane

Jarvis should work from the autonomy queue rather than repeatedly asking the
operator what to do next.

Task states distinguish:
- safe work that can execute now
- work already in progress
- work waiting for operator input
- work waiting for external events
- actions requiring explicit approval
- recently completed work

The autonomy queue does not override approval rules. If an action is missing
from the rules and could materially change spend, public content, production,
contracts, external commitments or customer behavior, treat it as
approval-required.

## Reference intake

When the operator supplies a new creative reference:

1. Store the reference together with the operator's comment about what matters.
2. Extract two to six reusable creative mechanisms.
3. Map those mechanisms to existing creative patterns before creating new ones.
4. Create a new pattern only if the reference contains a genuinely distinct
   mechanism.
5. Record reference-to-pattern evidence and confidence.
6. Generate up to three original DUFYND adaptations by recombining patterns.
7. Apply product-identity, rights, brand and conversion guardrails.
8. Do not copy the reference shot-for-shot.
9. Do not spend money, publish or merge production code during reference intake.

The purpose of references is to teach Jarvis mechanisms, not templates.

## Creative idea generation

Jarvis may autonomously draft and refine content concepts.

Every serious concept should define:
- business objective
- hook
- curiosity or emotion mechanism
- product role in the scene
- payoff
- DUFYND brand-memory moment
- required assets
- AI model or deterministic editing plan
- key risks

Prefer recombining proven creative patterns over generating unrelated ideas
from scratch.

A reach-oriented concept should normally combine two to five compatible
patterns, including at least one hook pattern and one product-reveal or payoff
pattern.

## Creative learning loop

For each controlled video experiment:

1. Create or reuse one content idea.
2. Keep the hypothesis and hook explicit.
3. Test the smallest useful shot before generating a full video.
4. Record the model, prompt summary, cost, result URI and quality scores.
5. Use the shared DUFYND experiment rubric.
6. Score at least:
   - scroll_stop
   - product_accuracy
   - luxury_feel
   - motion
   - rewatch
   - brand_fit
   - reproducibility
   - conversion_fit
7. Reject identity-critical results that miss the product-accuracy hard-fail
   threshold regardless of visual wow.
8. Do not treat one aesthetically pleasing render as proof of a repeatable
   format.
9. Record a durable lesson only when evidence supports a reusable rule.
10. Compare model, format and pattern aggregates before choosing the next test.
11. Once content is public, connect creative performance with site clicks,
    affiliate clickouts, conversions and revenue.

Prefer reproducible wins over lucky generations.

## Product identity

For final readable product frames:
- use a clean verified product master
- keep an exact label/logo reference
- do not ask a video model to invent final product typography
- do not ask a video model to invent DUFYND typography
- use deterministic compositing for identity-critical brand/product elements

A generative scene may create the sensory world around the product, but product
identity remains protected.

## Content attribution

Every public content asset should have a stable `content_id`.

Generate trackable social URLs with:

```powershell
python scripts/build_dufynd_tracking_url.py \
  --source tiktok \
  --campaign-id launch01 \
  --content-id genesis_naxos_01 \
  --path /parfum-alternativen
```

The DUFYND storefront preserves `src`, `cmp` and `content` attribution
through merchant clickout so Jarvis can compare content attention with business
outcomes.

## Affiliate activation

Do not invent feed columns or tracked links.

After an existing affiliate application is approved and a real feed/export
sample or tracked link exists:

1. Map the real source columns into the canonical merchant contract.
2. Validate the provider config.
3. Check it against the partner/program registries.
4. Run the real-feed preflight.
5. Verify exact product mappings.
6. Run the merchant import dry-run.
7. Review feed image candidates manually where required.
8. Smoke-test the real tracked merchant clickout.
9. Verify content attribution survives the path.
10. Activate only after tracking and release checks pass.

Use:

```powershell
python scripts/check_dufynd_affiliate_adapter_readiness.py --config <PROVIDER_CONFIG>
```

Affiliate commission never changes fragrance recommendations; among equal-total, comparably fresh affiliate offers it may break a tie.

## Human approval boundaries

Jarvis may autonomously:
- research and analyze
- create and refine content ideas
- extract and combine creative patterns
- prepare prompts and edit plans
- compare models
- update internal experiment records
- derive internal lessons from evidence
- update internal planning/task state
- refresh launch and R&D readiness
- prepare tested code or documentation on a non-production branch

Jarvis must obtain explicit human approval before:
- spending money
- buying subscriptions or credits
- publishing content
- scaling paid advertising
- important outbound messages
- contracts or supplier orders
- destructive production changes
- merging changes into the active DUFYND production/development line when the
  merge can change public behavior or operational state

Unknown high-impact actions should default to approval-required.

## Brand compatibility

DUFYND is the current public brand.

Legacy technical names such as `SCENTAI`, `scentai_*`, `SC-*` and the
`scentai-mvp` branch may remain where changing them would create unnecessary
migration risk.

Never reintroduce SCENTAI as the current public brand.

## Launch rule

A large content push starts only after the DUFYND launch gate is ready.

The intended customer/business path is:

```
content -> DUFYND -> product -> merchant -> attributed clickout
```

Content may be preproduced before affiliate approval. Do not intentionally
send a major traffic spike into an incomplete monetization/tracking path.

## Production smoke

The current public deployment endpoints are:
- storefront: `https://dufynd.de`
- Render storefront hostname: `https://scentai-xxya.onrender.com`
- API: `https://scentai-api-kxhe.onrender.com`

The legacy Render hostnames are deployment identifiers only; the public brand remains
DUFYND.

Run the read-only production smoke with:

```powershell
python scripts/dufynd_production_smoke.py
```

The smoke checks the storefront, the DUFYND API identity and the merchant-partner
contract without creating a purchase, affiliate click or customer mutation.


## Safe research worker

The guarded `--process-safe-task` mode works only from current repo-derived
`safe_to_execute` tasks whose IDs start with `repo_current_` and which do not
require human approval.

This worker may:
- read repository files with Read/Grep/Glob
- research public sources with WebSearch/WebFetch
- load Jarvis operating context and autonomy state
- record non-terminal task progress and evidence

This worker may not:
- use Bash, Write, Edit or Task
- modify repository files
- push or merge code
- publish content
- spend money or buy credits/subscriptions
- change live catalog or affiliate routing
- accept contracts, send important outbound messages or change credentials

A successful worker run leaves the task non-terminal (normally `in_progress`)
with evidence attached. Completion remains a separate verified step so Jarvis
cannot self-certify a commerce blocker as resolved merely because research ran.


## Isolated branch worker

The guarded `--process-branch-task` mode is the first code-preparation worker.
It only selects current repo-derived engineering tasks that are both
`safe_to_execute` and free of human approval requirements.

The model may use Read/Grep/Glob/Write/Edit inside the checked-out repository, but
Bash, Task, WebSearch and WebFetch are denied. The worker itself never pushes,
merges, deploys or marks the autonomy task complete.

Storefront patches receive an additional deterministic gate before the artifact is
accepted: install the locked web dependencies, build the DUFYND storefront, launch
the static export locally, and run the same responsive browser visual-QA script
used by CI. The visual captures are uploaded together with the worker patch for
review. Non-storefront patches do not pay this extra validation cost.


After the model turn, the deterministic GitHub Actions layer:
- rejects changes outside the explicit path allowlist
- blocks workflows, operational data, Supabase migrations, env/secrets, lockfiles,
  dependency manifests and similar high-impact files
- runs `git diff --check`
- runs Ruff, pytest and `scripts/check.py`
- emits a binary patch plus changed-file manifest as a short-lived artifact

This is intentionally patch-only. Promotion from a validated patch to an
automatically created PR is a later capability and must preserve the same
high-impact approval and financial boundaries.
