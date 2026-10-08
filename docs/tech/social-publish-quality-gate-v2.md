# DUFYND Social Publish Quality Gate V2

Purpose: no social post may reach scheduling/publishing merely because media and copy exist.

## Hard gates

A candidate reaches owner approval only when all of the following are evidenced:

1. Product truth and exact variant match.
2. Rights and factual-claim review pass.
3. Final upload asset digest is frozen and matches the reviewed asset.
4. Visual quality is at least 9.5/10.
5. Final media is at least 1080 px on both axes.
6. Native mobile preview is verified for crop, safe zones, readability and compression.
7. Platform click path is real:
   - Instagram feed/reel/carousel: do not treat caption URLs as clickable. Use verified profile-link CTA.
   - Instagram Story: a verified link-sticker path may be used.
   - TikTok without a clickable website surface: no raw URL CTA; use engagement/profile CTA only.
   - YouTube: video required; CTA must use an actually supported clickable/profile surface.
8. Owner approval remains separate. Passing QA never authorizes scheduling or publishing.

## Incident rule

If a live post fails any hard gate after publication, treat that publication as an invalid launch attempt for creative-quality evaluation. Preserve analytics evidence, but do not use the attempt as the clean baseline for the replacement creative. The replacement receives a new content revision/identifier and a fresh owner gate.

## Current remediation

The 2026-10-05 1 Million Instagram image post exposed two failures:
- final live image quality was below the Owner standard;
- a raw caption URL was presented even though that is not a clickable Instagram feed surface.

The scheduled TikTok sibling was stopped before auto-publish. Any replacement must pass this V2 gate before it can be presented for Owner approval.

## Mandatory platform-audio gate (2026-10-08)

**Incident:** The owner reported an unsatisfactory, silent Instagram feed-image
meme and TikTok photo post on 2026-10-08. A later manual Instagram music
addition did not rescue creative quality. Recording a successful publication
is not the same as a passing viewer-experience review.

The offline `scripts/check_dufynd_content_review.py` now rejects every
Instagram/TikTok candidate without a frozen `publish_contract.audio_contract`
and explicit `content_kind`. A social meme cannot be intentionally silent.
Independent evidence is required for **audible mobile preview, commercial-use
music rights, an audio score >= 9.5, and exact media binding**. Every change
in song, timing, volume or media rehashes the frozen package and invalidates
its prior review. This is an **offline gate**, not a platform scheduling
credential or a guarantee that a video is audibly correct. Actual playback
must be independently listened to, and the live public post must be QA'd
after publication.

### Instagram: two supported paths

1. **Preferred unattended Reel:** Prepare a real vertical 9:16 video with
   an audible, legally cleared soundtrack already embedded as AAC in MP4,
   and verify full playback, rights, final digest and mobile preview.
   `audio_contract.mode=embedded_video`, `delivery=metricool_auto`.
2. **Metricool Meta-library Reel:** Metricool supports
   `instagramData.type=REEL` together with
   `instagramData.audioConfiguration.audioId` for an Instagram Business
   account connected via Facebook. The exact track ID, listening preview,
   commercial music rights and account connection must all be verified;
   never fabricate an ID, inferred connection or track clearance. The
   local offline gate requires `mode=metricool_reel_library` and
   `facebook_connection_verified=true`.
3. **Static Instagram meme/image/carousel with native sound:** Metricool's
   automatic photo POST upload does not add Instagram native music.
   Use native Instagram app music selection (or the
   Metricool notification/manual handoff) and review the selected track
   *before* the final manual publication. `mode=instagram_native_music`;
   `delivery=instagram_native_app` or `metricool_notification`.
   **Do not use** `instagramData.audioConfiguration` on POST: it applies
   to REEL/TRIAL_REEL only.

### TikTok

- Photo posts require preselected, auditioned, commercially usable native
  sound and a manual/native handoff (`tiktok_native_music`).
  `autoAddMusic=true` alone is **not** an acceptable 9.5-quality guarantee:
  the platform can choose an unreviewed sound.
- Actual 9:16 videos with an independently verified embedded soundtrack
  may be scheduled as videos (subject to current account eligibility).

### Release and post-publication

A quality pass returns `READY_FOR_OWNER_APPROVAL`, **never publication
authorization**. Verify media MIME/width/height, safe zones, full audible
playback, volume, timing at punchline, attribution/rights, cover, caption,
commercial and AI labels, account connection and real public URL.
After publication check public video/photo **on the actual platform with
sound unmuted**. A publishing success flag, a JPEG upload or even an
audio track identifier does not prove audible output. No deletion, silent
reupload, replacement or auto-publish without new specific owner approval.

References (retrieved 2026-10-08):
- https://help.metricool.com/how-to-add-audio-to-your-instagram-reels-from-metricool-2o2ks
- https://help.metricool.com/schedule-and-post-on-instagram-6b6q5
- https://help.metricool.com/publishing-requirements-for-images-and-videos-from-metricool-vfc8n
