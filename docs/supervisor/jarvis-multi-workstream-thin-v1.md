# Jarvis Multi-Workstream Orchestration — Thin V1

## Purpose

Reduce Owner routing work without changing DUFYND's business objective or safety gates.

North Star:

`Reach -> qualified traffic -> product views -> merchant clickouts -> transactions -> commission -> learning -> scale -> profit`

The CEO Radar remains the business-priority layer. Jarvis is the operational orchestrator.

## Thin V1 contract

Jarvis coordinates the existing workstreams through the existing Supabase control plane:

- revenue / affiliate
- content
- web / CRO
- platform / tech
- deterministic supervisor work

It must use current live state, explicit task dependencies, resource scopes, durable evidence and existing owner gates.

### Selection rules

1. Reject stale or non-green tasks before execution.
2. Prefer no-spend deterministic work when a certified free handler exists.
3. Use task priority and current CEO business state; do not invent work merely to keep a worker busy.
4. Preserve TECH lease/resource conflict rules.
5. Never infer completion without evidence.
6. Owner-gated actions fail closed.

### Owner gates

Thin V1 does not authorize:

- paid model calls, credits or paid tools
- social publishing
- public product activation
- external outreach, contracts or legal commitments
- destructive or irreversible changes
- changes to `main`

### Current business state

At bootstrap on 2026-10-04:

- Rabanne 1 Million EDT 100 ml is the first live First-Money experiment.
- Instagram is scheduled for 2026-10-05 10:00 Europe/Berlin.
- TikTok is scheduled for 2026-10-05 18:00 Europe/Berlin.
- Delina EDP 75 ml is live and visually finalized.
- PR #671 established first-party session continuity, Awin clickrefs and CJ SID-based per-click attribution.
- Real transaction and commission proof still require authoritative network evidence. Clickouts are not sales.

The authoritative live business checkpoint is `continuity.checkpoint.ceo_radar` in `dufynd_master_status`.

## Acceptance

Thin V1 is accepted only when:

- one certified free durable task is persisted independently of chat state,
- an authorized runner claims it with immutable capability/resource fencing,
- checkpoints are persisted,
- deterministic verification completes,
- the task ends terminally with evidence,
- no paid provider call occurs,
- no Owner gate is crossed,
- no `main` change occurs.

This acceptance proves the chat-independent control plane, not arbitrary autonomous business execution. Additional worker capabilities must be added narrowly and only after their deterministic safety contract exists.
