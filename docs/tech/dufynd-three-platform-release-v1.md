# DUFYND release contract V1

Every short has one release content ID and three platform-specific asset content
IDs. The existing unique content-ID index remains intact; the revision-bound
`metadata.release_content_id` groups exactly three asset rows:
`instagram` (reel), `tiktok` (video), `youtube` (video/short). Photo releases
contain Instagram and TikTok only and stay in their native handoff workflow.
Registration and preparation never approve or schedule anything.

The existing content workflow and exact `content_publish_go` remain required
per asset. `release_contract_v1` binds the title, AI disclosure, audio source and
commercial visual-rights evidence to the existing revision fingerprint; existing
commercial music, listening, independent QA and immutable SHA gates still apply.
YouTube now runs the same audio checks. Approval is never synthesized or copied
from another platform, date, caption or revision. `READY` means both technical
checks and the concrete private Control Room publishing decision are valid.

Use `dispatch_connected_release` in the existing Metricool connector adapter.
It checks every platform, hashes every local and hosted file, constructs all
three provider payloads and atomically reserves the release before any call.
The previous single-asset reservation fails with `release_dispatch_required`.
A claim immediately before each call rechecks revision and Owner GO. A repeated
claim, reservation, timeout, lost receipt or crash cannot cause a second call.
A partial failure retains known `SCHEDULED` rows, sets the failed row to `FAILED`,
holds remaining rows `BLOCKED` and halts the parent. Reconcile native/provider
state manually before any recovery; there is deliberately no automatic repost.
Cross-platform providers cannot offer an atomic public publish transaction.

Persistent states are `READY`, `BLOCKED`, `SCHEDULED`, `PUBLISHED`,
`AUDIO_VERIFIED`, `FAILED`. A Metricool planner ID is not a native platform ID.
`record_release_verification` validates native URL/ID, source SHA, platform-output
SHA, independent checker and media identity before `PUBLISHED`. Separate full
playback, waveform match, timing and actual listening evidence are mandatory for
`AUDIO_VERIFIED`. A successful HTTP response or waveform alone is insufficient.
Neither this service-only contract nor the adapter intercepts direct third-party
Metricool UI/MCP usage. The connected host must use this entry point; no new
worker, paid API key, scheduler or blanket publication authorization is created.

Provider schema checked on 2026-10-10 against the public Metricool Swagger:
https://app.metricool.com/api/swagger.json . AI fields: Instagram `isAiGenerated`,
TikTok `isAigc`, YouTube `isAiGeneratedContent`. The receipt must echo the exact
AI setting, title, media URI, caption, date and automatic-publish flags.

## First-money provenance

QA enters through `?qa=1`, persists in session storage across navigation, travels
on all analytics payloads and clickout URLs, and is classified before session
hashing. Existing QA/test/smoke/preview identifiers are also excluded. New events
are `visitor` or `internal_qa`; historical unproven traffic is `unclassified`, not
retroactively declared real or organic. A QA mark excludes the entire hashed
session from visitor reporting. Both first-money readers and the signal trigger
use the new provenance. Attribution is not proof of a human, organic reach,
purchase or commission; affiliate transaction ingestion remains required.

## Le Male Elixir, 2026-10-11

Preparation is stored privately under `content.le_male_elixir_release_20261011`.
The unchanged existing social export SHA is
`4e2065ef9dac2f68d772d8e54da0476b27ec8d5e48d6a7dde719a8e9e4804715`.
No public post, binding schedule, new creative or owner decision is created.
Original soundtrack identity and commercial licence are undocumented. Technical
container duration is 10.080s versus 9.750s video; AAC is 193889 bit/s, above the
existing internal 128k audio gate. No listening or 9.5 quality score is invented.
A separate proposed free replacement is Kevin MacLeod's **Bossa Antigua**, ISRC
USUAN1700069, CC BY 4.0 with attribution and adaptation notice. Applying it would
change the export and needs an explicitly reviewed new SHA, complete QA and GO.
The current original is preserved. Sources:
https://incompetech.com/music/royalty-free/index.html?Search=Search&isrc=USUAN1700069
https://incompetech.com/music/royalty-free/pieces.json
https://creativecommons.org/licenses/by/4.0/
