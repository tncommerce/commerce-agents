# DUFYND audio publishing — 2026-10-09

## Delivered

An opt-in publisher now revalidates the existing visual/audio/rights gates and freezes the exact MP4 hash, asset revision, caption, platform and time. A visual review is insufficient: a separate `content_publish_go` is approved through the authenticated private Control Room. The UI exposes the exact file, hash, caption and time. The SQL reservation is durable before any Metricool call; uncertain results remain on hold and cannot be retried automatically. Duplicate content IDs and source hashes are blocked per platform/brand.

The service-role-only migration has been applied to production. Its fixture matrix was exercised in a rollback transaction: no real approvals, dispatches or social posts were created. The Python dispatch path and owner controls are delivered as source; a continuously running connector adapter is **not deployed**.

## Enforceable boundary

The database gate cannot intercept direct Metricool connector calls or actions in its web UI. Such calls must be routed through this publisher by the operator. No account-wide protection is claimed. The Python `metricool_schedule` adapter must use the connected tool and normalize a full provider echo. `verify_hosted_media` must safely fetch and hash immutable, allowlisted media; an HTTPS URL containing a hash alone does not establish immutability. No paid Metricool API access is required or purchased.

The adapter callbacks are explicit integration requirements, not an already operational worker. After Owner GO, scheduling still requires attaching that runtime adapter and an immutable-media verifier. No public testing is authorized by development approval.

## Measured QA

`audit_media` checks SHA-256, 9:16, at least 1080×1920, 8–15 seconds, H.264/yuv420p, frame rate, AAC bitrate/sample rate, full A/V decode, measured loudness/peak and audio duration. It cannot prove genuine source motion, native resolution, humor, licenses, independent listening or a 9.5 visual score.

`compare_audio` compares decoded source/output waveforms and alignment. Real codec tests accept AAC transcoding and reject silence, replaced sound, 160 ms shifts and truncation. The technical 12-second color-pattern/tone fixture is clearly marked as a test; it is not a Reel candidate. Public playback validation additionally requires an actual published platform URL/post ID, output hash, independent checker and listening/timing evidence. A schedule is never recorded as a passed publishing E2E.

## Live evidence and blockers

- PR #752: seven jobs passed, merged to `scentai-mvp`; Render API deployment `dep-db42qdojo6nc73bnakf0` live on `c2a5fd1b745090c1239929265b9e7bd05775822f`.
- PR #750: seven jobs passed; reviewed and merged as `49656521e049361b70f6b40de8ec2d716297eed8`. Image approvals stop being requested repeatedly; affiliate purchase gates remain closed.
- Metricool connected `dufynd` professional Instagram and personal TikTok. In an unsaved Reel editor, Audio hinzufügen returned: “Erfordert Instagram über Facebook verbunden” / “Verbinde dich mit Facebook”. No media or post was saved. Connecting Facebook requires the Owner's account login/permissions.
- Embedded audio avoids native music selection, but still requires a genuine qualified final video, commercial sound-rights evidence, independent audible review and exact publishing GO.
- Existing Naxos master is 720×1280, 3.04 seconds and silent; frozen photo memes and animated slideshows do not qualify as genuine high-quality video. No 9.5 score was invented.
- top Parfümerie: membership/feed readiness does not prove affiliate tracking. No offer activated; fresh variant stock, a valid per-variant Awin destination and clickref/transaction evidence remain necessary.

## Operating sequence

1. Register a new genuine-motion final MP4 and immutable public hash URL; keep existing frozen creatives unchanged.
2. Attach measured media QA, rights evidence, soundtrack/punchline review and independent visual/listening QA. Existing workflow must become owner-approved for that exact revision.
3. Call `request_dufynd_publish_go_v1` only for a fully ready candidate. Owner reviews the exact file with sound and approves the separate public action.
4. Connected executor calls `PublishOrchestrator.dispatch`; reservation precedes the single Metricool call. Ambiguous response → reconcile manually, no repeat.
5. Only actual Instagram/TikTok publication plus independent platform-output playback evidence passes post-publish QA.

This remains readiness work until steps 1–3 and the runtime adapter are complete. No automatic daily publishing or public E2E success is claimed.
