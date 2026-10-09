# Jarvis Dashboard V2 — dense operator cockpit

Implemented from the saved brief `jarvis.dashboard_dense_v2_brief_20261009`.
Base: `096a17f926f28e74279b645efdfdd011aa23160f`, branch `scentai-mvp`.
The observed `main` head was `37727be7994ebb3fc3881f8adb06d8596774e2ad`.

## Interface

Desktop has compact left navigation, a central current-priority/work surface and a
narrow Jarvis/system rail. The overview promotes observed active workers, work
count, Owner gates, last loop and last verified completed Worker checkpoint. The
output summary explicitly distinguishes a completed Worker output from observer
signals; absence is shown as missing evidence, never an invented success.

The four primary mobile destinations are Jetzt, Worker, Blocker and Systeme with
fixed bottom navigation. They select actual views instead of scrolling a desktop
page. First Money and technical details remain accessible from Systeme. Existing
hash links work, including direct technical links. Navigation and disclosures retain
keyboard access, visible focus and reduced-motion behavior. Polling preserves the
selected view and open evidence. The Systems destination promotes its source
cards into the central surface rather than leaving an empty workspace.

Worker cards keep the current task, execution state and next documented step
visible; technical identity, exact lease/heartbeat and previous checkpoint are
expandable. The four organization groups remain distinct, with the full roster
available on demand. Unknown steps and absent timestamps remain unknown.

A failed snapshot clears current worker/task/gate counters. Previous Worker cards
and source badges become explicitly historical; the global risk banner removes
any current-health claim. Recovery rebuilds these from the next valid snapshot.
No authentication, CSRF, permission, handler, publishing, model, budget or
orchestration contracts are changed. No new dependencies, services, paid calls,
schedules, assets or database migrations are introduced.

## Verification

- Full local Python suite: 3,162 passed, 185 skipped (environment/integration gates).
- Ruff lint/format and repository consistency checks passed.
- Existing control-room regression replay extended to 320/390/430/768/1280/1440.
- New V2 replay covers navigation by keyboard, focus and expanded evidence across
  refreshes, active/idle/wait/Owner/error/stale states, failure and recovery,
  reduced motion, unique IDs, responsive overflow and deep links.
- Sixty full-page V2 screenshots were generated from isolated server-built DTO
  fixtures. These are test scenarios, not live production screenshots. Every
  request is intercepted locally; the replay asserts zero write/provider calls.
- At 844px viewport height, the current-work section begins within the first
  viewport at all six widths. The output summary is also within the first viewport
  in the active fixture. Real task length and number of gates can increase height;
  the brief's 70–80% mobile density target is a design goal, not a fabricated KPI.
- Production `/api/health` responded successfully before the change, and anonymous
  `/internal/jarvis` redirected to `/internal/login`. Actual owner-session/voice
  calls were not executed; production deployment needs separate release evidence.

Reproduce (Playwright/Chromium must be available; no paid services):

```sh
PYTHONPATH=examples:. python tests/browser/build_control_room_fixture.py /tmp/room-v2.json
node tests/browser/control_room_evidence.cjs /tmp/room-v2.json
node tests/browser/control_room_v2.cjs /tmp/room-v2.json
```

Both browser scripts accept `CONTROL_ROOM_QA_CHROMIUM` for an existing Chromium
binary and `CONTROL_ROOM_QA_OUTPUT` for screenshots; defaults use temporary folders.
No generated fixture or screenshot enters production assets.


## V2.1 — Owner feedback, 2026-10-09

Updated the existing dashboard from branch head `4c029f1`, using both original
references in `/DUFYND/Jarvis/References/2026-10-09`. No alternate mock, dependencies,
providers, infrastructure, migrations, worker dispatches or changes to `main`.

- One consolidated V2.1 CSS layer replaces the accumulated V2 tail overrides.
  Descriptions use 12–14 px, major values 18–22 px. Jarvis voice is compact.
- Priority, Owner gates, First Money, costs, current execution, last verified output
  and next checkpoint/plan are visible in the first 1440×900 desktop viewport.
- Mobile uses independent Jetzt, Worker, Freigaben, Systeme destinations. The
  start view places work before a concise business summary. Technical dependencies,
  the full role roster and observer signals are native disclosures.
- The first execution shows its actual verified checkpoint and documented next
  step. Missing checkpoints/results remain explicitly missing. Additional executions
  link to the Worker view; roles never count as executions. Common stored audit
  titles have German display labels, with original identifiers preserved in evidence.
- Verified completions are separate from observer heartbeats. The receipt time
  no longer substitutes for snapshot time. Source timestamps include dates and
  degraded sources sort before healthy sources.
- Freigaben stays useful with zero gates. Owner review does not float over the
  decision controls. Deep links expand enclosing dependency disclosures.
- Live data inspection found a persisted replacement publication schedule from
  October 5 still displayed as planned on October 9. After the existing 20-minute
  schedule grace period, the read-only projection now marks publication unconfirmed.
  It preserves Owner GO, replacement identity, attribution and stopped original
  history; it never publishes again or invents an additional Owner gate.

### Verification and limits

Full local Python suite: **3,165 passed, 185 skipped**. The skips are existing
integration/environment gates. Added regression coverage for future/elapsed
replacement schedules, preserving authorization and unknown sale/commission.
Existing auth, CSRF, logout, Owner-action and voice contract tests remain intact.
Browser replays cover failure/recovery, active/wait/idle/Owner states, keyboard,
focus retention, disclosures, deep links, reduced motion and horizontal overflow.
The acceptance replay now includes 1920 px as well as 320/390/430/768/1280/1440.

`tests/browser/control_room_capture.cjs` captures seven widths and all four primary
views from an externally supplied sanitized snapshot, including viewport/full-page
images, source and image hashes, and measured content positions. It intercepts
all requests, requires GET, and rejects external origins. Important live-data
summary elements must fit one desktop or two mobile viewports. No capture data,
Owner credentials, tokens or screenshots are committed to this public repository.

The live-data replay uses the production `DashboardReader` projection and the
same allowlisted database columns, exact count bounds and read-only First Money
runtime. Decision tokens are omitted, no budget identity is guessed, and missing
budget-window data remains unknown. Reads are non-atomic as in production.

Production anonymous access was checked: health succeeds, the dashboard redirects
to Owner login, snapshot returns 401. This environment has no authenticated Owner
session. Screenshots therefore represent the actual application rendered with
captured live data, **not an authenticated production browser session**. Voice
configuration in the captured template is disabled; no paid voice or real business
approval/publication was invoked. Green CI and deployed byte verification are
recorded separately after pushing the development branch.
