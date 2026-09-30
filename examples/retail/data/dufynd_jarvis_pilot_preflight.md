# DUFYND Jarvis Paid-Pilot Preflight

This command is a deterministic, read-only control check for an already approved
Jarvis paid-pilot budget window.

It does **not** start Jarvis, consume model budget, mutate queue state, change the
approved budget, publish content, alter affiliate routing or deploy anything.

## Purpose

The retrospective deliberately reports historical warnings such as a prior failed
run or a prior per-run-cap breach. Those are useful for review, but they should not
automatically make a currently valid approved budget window unusable.

The preflight therefore separates:

**Hard blockers**
- invalid or missing human approval;
- budget-window scope above its human approval;
- run-count reconciliation failure;
- spend reconciliation failure;
- inconsistent report sources;
- no remaining approved runs;
- no remaining approved budget.

**Warnings**
- historical per-run-cap breach;
- failed-run spend;
- near-per-run-cap activity;
- other non-control retrospective attention.

A preflight is `ready: true` only when all hard controls are intact and approved
run/budget headroom remains.

## Usage

```bash
python -m scripts.check_dufynd_jarvis_pilot_preflight --pretty
```

The command exits:

- `0` when the already approved pilot controls are ready;
- `2` when a hard control blocks paid execution.

This command is intentionally not wired into the Nightshift dispatcher in this
change. Dispatcher/runtime integration is a separate control-plane change and
should remain independently reviewed to avoid collisions with active Jarvis work.
