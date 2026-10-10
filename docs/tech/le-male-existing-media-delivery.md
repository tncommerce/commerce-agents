# Existing Le Male Elixir delivery — 2026-10-10

Scope: existing owner-final media only. No media is committed, uploaded publicly,
normalized, transcoded, scheduled or published by this change.

## Provider requirements versus internal policy

- YouTube: Metricool accepts vertical MP4 Shorts up to 3 minutes and 500 MB.
  YouTube lists AAC-LC, 48 kHz and 24 fps among recommended upload settings;
  stereo audio at 384 kbps is itself a recommendation. A shared 128 kbps maximum
  is therefore incorrect.
- TikTok: Metricool explicitly calls 128 kbps recommended. TikTok's media guide
  permits H.264/MP4, 23–60 fps, dimensions 360–4096 and up to 4 GB; the stricter
  Metricool size/duration limits still apply.
- Instagram automatic: retain the documented Metricool 128 kbps profile.
  Do not assume the YouTube/TikTok change proves Instagram acceptance.
- Instagram native: gallery upload and draft save are documented by Meta.
  General Instagram Reels guidance says minimum 30 fps; this exact media is
  24 fps. Without an actual non-public native import/preview, native acceptance
  remains unverified. No frame-rate conversion is authorized.

Sources checked 2026-10-10:
- https://help.metricool.com/publishing-requirements-for-images-and-videos-from-metricool-vfc8n
- https://help.metricool.com/schedule-and-post-on-instagram-6b6q5
- https://support.google.com/youtube/answer/1722171?hl=en
- https://developers.tiktok.com/docs/en/content-posting-api-media-transfer-guide
- https://www.facebook.com/help/1038071743007909
- https://about.fb.com/news/2020/08/introducing-instagram-reels/

## Minimal correction

The validator now receives the actual platform from both dispatch entry points.
Its default remains Instagram. YouTube/TikTok no longer inherit the 128 kbps
ceiling. Full decode, sample rate, duration, file hash, finite loudness and
true-peak checks remain enforced.

The -20 to -10 LUFS target is internal quality policy, not a provider hard limit.
Only SHA-256
`4e2065ef9dac2f68d772d8e54da0476b27ec8d5e48d6a7dde719a8e9e4804715`
has a narrow -21 to -20 LUFS preservation exception for YouTube/TikTok, tied to
`content.le_male_elixir_owner_final_no_audio_changes_20261010`.
It preserves the already accepted -20.89 LUFS mix. Different bytes, silent or
nonfinite audio, clipping, decoding errors and duration changes still fail.
This is not a general quality waiver, new listening claim or publishing GO.
Instagram is not included.

Read-only execution against the actual private social file passed YouTube and
TikTok: H.264/yuv420p 1080x1920, 24 fps, AAC 48 kHz stereo, 193889 bit/s by
ffprobe (193 kb/s rounded in FFmpeg), -20.89 LUFS, -5.65 dBTP, 10.08 s container.
Instagram still fails its automatic audio profile. Source hash unchanged.

The existing owner approval, durable duplicate reservation, hosted-byte
verification, three-platform preflight and post-publication audible-playback
requirements remain unchanged. A local file PASS is not operational readiness.

## Media handoff and private native fallback

The source already exists privately in the release's existing file records.
The Supabase project currently has no Storage buckets. The current Drive view
URL is not a content-addressed MP4 URL. Do not mark it immutable or public-ready,
expose a private download token, put the video in this public repository, or
create another hosting service. Public media availability has to be explicitly
covered by the subsequent exact release GO and verified before automatic
dispatch; the present task does not authorize public upload.

For Instagram, use the existing Social MP4 on the Owner's phone as a single
gallery clip in @dufynd. Preserve full duration, original audio/SFX and volume;
do not select music, templates, remix, filters or auto edits. Apply the existing
caption and AI disclosure. Save a private draft and stop before Share/scheduling.
Record whether the native app accepts the 24 fps source and whether full
playback retains the original sound. Reject/stop on any media conversion
request or sound loss; do not create a replacement.

There is no mobile-app control in this execution environment. The native import
test must be performed on the actual phone; browser/Metricool draft acceptance
would not prove mobile-native acceptance.

Proposed slots remain 2026-10-11 Europe/Berlin: YouTube 16:00, Instagram 18:00,
TikTok 18:30. Existing platform content IDs, captions and AI flags remain
authoritative in Supabase. No real dispatch or approval is created by tests.

