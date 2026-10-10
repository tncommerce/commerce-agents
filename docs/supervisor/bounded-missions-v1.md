# Bounded Jarvis missions

`start_dufynd_mission_v1(id, 'zero_budget_content_preparation')` accepts one
explicit internal business goal. It creates a persistent two-step plan on the
existing task and worker plane. It is a deterministic certified-handler mission,
not an unrestricted agent or a media-generation pipeline.

1. `content_backlog_prioritize` ranks the current planned ideas into NOW, HOLD
   and PAUSE, preserving the full queue as an immutable mission result.
2. `content_production_packet` builds a concrete brief for the exact selected
   idea, including its concept, hook, copy/visual direction and quality gates.

The existing ten-minute CEO cron runs one step per invocation through
`run_dufynd_ceo_with_missions_v1()`. When no mission is runnable it falls back to
the existing safe CEO cycle. Eleven cron jobs remain; no new provider is used.
An authorized operator can also call `tick_dufynd_mission_v1()` for an immediate
bounded step. Only `service_role` and `postgres` have RPC execution privileges.

Each step checks the enabled certified free contract, respects conflicting
leases, creates its child task just in time, and invokes the existing fenced
worker. Completion requires the exact task, released lease, real full evidence,
fresh artifact, zero spend and publication disabled. The second result must
match the first result's selected idea. The 9.5 target is a future creative QA
gate, **not** a claim that generated media has passed visual review.

Results live at `jarvis.mission_result.v1:<id>:1` and `:2`; the plan and
checkpoints at `jarvis.mission.v1:<id>`. Task IDs are `mission:v1:<id>:1` and
`:2`. These are durable snapshots in addition to the workers' mutable latest
outputs. Restarting the same ID returns its prior state without repeating work;
another active mission with the same goal is deduplicated.

A failure rolls back the whole current step (including its lease and writes)
while preserving earlier checkpoints. Retry delays are 120 and 240 seconds,
with at most three attempts. Missing predecessor, changed contract and failed
artifact QC block immediately. Active resource leases wait without consuming
attempts. One alert at `jarvis.mission_alert.v1:<id>` preserves its first-seen
time and resolves on successful recovery. It does not send email.

Blocked missions retain evidence for inspection. Correct the underlying cause,
then use a new explicit mission ID; never mark a child done or edit an artifact
to bypass verification. Publication, paid generation and product activation
remain outside this mission. After completion, the next step is visual selection
or creation and fresh creative QA through the existing approval mechanisms.

The PostgreSQL integration suite exercises the real existing worker functions,
two completed artifacts, active/expired leases, stale-token rejection, rollback,
retry backoff, checkpoint recovery, terminal failure, idea drift, alert
deduplication, disabled contracts and denied anonymous execution.
