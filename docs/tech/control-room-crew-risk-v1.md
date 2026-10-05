# Control Room crew and risk view

The main owner overview shows global risk before Jarvis, followed by decisions,
current/next work, the crew, First Money, workstreams and activity.

The crew is an organisational model, not a list of running processes. Its fixed roles are:

| Cluster | Names and functions |
| --- | --- |
| Build | Zoro: Tech; Franky: infrastructure; Chopper: QA |
| Money | Nami: revenue/analytics; Law: attribution; Brook: affiliate |
| Growth | Sanji: content; Robin: rights/research; Usopp: external response tracking |
| Operations | Jinbe: queue/dependencies |

Documented handler function takes precedence over a generic executor alias. Unknown
execution roles remain explicitly unassigned. Multiple instances aggregate into one
stable role node, with each execution identity available in details.

Active requires the existing valid lease, current heartbeat/progress and a complete
bounded operational read. A task assignment, reserved role or healthy supervisor alone
never makes a role active. Ready means an available organisational role; handler
certification and execution eligibility are separate and unchanged. Monitoring names a
verified source/loop, or an existing non-active execution. Waiting and blocked roles
carry actual task reasons and resolution paths. Task update time is labelled as such;
the exact status-transition timestamp is not stored. Pending decisions only create
Owner paths from actual decision/task records.

## Risk rules

Red: failed production smoke, failed current-head CI, unknown provider cost,
nonterminal stale execution/lease risk, documented credential reauthorization or
pending Owner decision. Red need not mean Owner action: the panel explicitly names
who can resolve it.

Amber: older evidence, unavailable/degraded noncritical observer, incomplete reads,
open reservations, merchant coverage or other blocked prerequisites. Gmail expiry
without a recorded reauthorization requirement is amber, never an invented Owner gate.
An older passed smoke is not an outage. An older failed CI on another head does not
prove current-head failure. Render observer freshness is independent of public
production availability. Missing essential production/loop evidence says the situation
is not fully confirmed, rather than declaring stable operation.

Blue: verified supervisor monitoring, active execution or classified First Money runtime.
Normal external waiting appears amber on the role to explain its dependency, but is not
an independent critical system incident. Green requires complete verified evidence;
unknown cost or incomplete Owner reads never become zero/no-action claims.

Panels cover production, GitHub/CI, Render, automation/leases, costs/reservations,
Gmail, affiliate prerequisites, First Money tracking and Owner decisions. They expose
why, evidence time, next step and Owner requirement without sending commands.
Transactions and commission retain the existing external-network-evidence boundary.

## Interaction and evidence

Desktop uses four clusters below Jarvis; mobile uses vertically ordered active,
waiting/blocked and other roles. Only actual active role paths animate. External paths
are amber dashed; Owner paths are red. Reduced motion disables crew animation. Native
expand controls work with tap/keyboard and retain open/focus state on refresh. Connection
loss removes active animation and global assurance; last-known roles are labelled.

`tests/test_jarvis_crew.py` covers risk severity, misleading historical evidence,
role purpose, unassigned executors, multiple instances, stable identities, cost
reservation discrepancies, bounded-read failure and sanitized data. The isolated
four-width browser replay additionally checks mobile ordering, drawer focus, reduced
motion, recovery, real/red test gates and absence of fabricated activity. Fixtures never
write to live data or trigger work.

No new dispatch handler, runtime policy, credentials, paid action, social action,
product activation or image asset is introduced.
