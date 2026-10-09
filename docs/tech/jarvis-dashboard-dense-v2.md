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
