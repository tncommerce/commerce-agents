# Audio-first production gate V3

The merged #751 checker was offline only. V3 connects its audio requirements to
`dufynd_content_publish_contract_v2_reason`, which the real owner-review RPC
already calls, and to the enrolled content workflow QA. It creates no publisher,
owner GO, schedule, public post, paid generation or asset backfill.

Required for Instagram/TikTok: evidenced commercial music rights, audition,
audio quality >=9.5, format-specific delivery and frozen asset hash. Actual video
requires >=1080x1920, exact 9:16 and genuine-motion review. Embedded audio needs
AAC, full playback, timing and loudness checks. Explicit revision-bound proof is
also required for duplicates, safe zones, sharpness/compression, platform caption
and sound timing. Changed metadata invalidates existing owner review and workflow
fingerprints through the existing mechanisms. Public playback verification now
requires a platform post ID, public URL, exact asset hash and audio playback proof.

## Supported delivery contracts

- Instagram Reel library: specific `audio_id`, verified Instagram Business and
  Facebook connection with evidence, selected and preheard track. Metricool's
  documented native feature is web-only, starts audio at zero and provides no
  combined video/music preview. `instagramData.audioConfiguration.audioId` is the
  intended provider field; this patch does not claim to have dispatched or tested
  that field through the connected scheduling tool.
- Embedded Instagram Reel / TikTok video: final-video digest matches the exact
  asset; AAC stream, full decode/listening, loudness and timing review required.
- Instagram image/carousel: native app or notification handoff; Reel audio
  configuration cannot make a photo auto-post musical.
- TikTok photo: selected, preheard native sound and manual/notification handoff;
  random `autoAddMusic` is insufficient.

Evidence booleans are contracts, not independent measurements. A maker cannot
invent hearing tests, licences or a 9.5 score. The authenticated owner gate remains
separate, and these RPCs always report `publishing_authorized=false`. An external
Metricool tool/UI call cannot be intercepted by a Supabase function: a future
publisher must invoke the gate before every dispatch. No end-to-end automated
publishing claim is justified until that integration, exact Owner GO and public
playback are verified.

## Live audit 2026-10-09 (Europe/Berlin)

- Base `scentai-mvp`: f65077d043bb491e74a1d078ad2ca1126919ffa2; postmerge CI success.
- #750 remains open; technical checks success, visual QA has no completed result
  in the initial observation. No merge of #750 in this patch.
- Metricool DUFYND 7182186: Instagram and TikTok connected by brand settings;
  connection type and commercial library track unverified. No future schedules
  returned for Oct 9 through Dec 31. Analytics returned Oct 1-7 Instagram photos
  and carousels; analytics absence does not prove an Oct 8 post is absent.
- Frozen Phone Suspicion and Fourteen Fragrances assets remain untouched.
- Existing Naxos motion V2 downloaded from its stored URI: 720x1280 H.264, 24 fps,
  3.04 sec, no audio stream, full FFmpeg video decode succeeds. Rejected for the
  requested >=1080x1920 master and audible soundtrack. Do not disguise upscaling
  or loop a short test as a completed premium Reel.
- top Parfuemerie: approved/feed-ready, tracking-ready=false. Merchant feed/image
  email evidence is for affiliate integration, not blanket social-ad rights.
  Notino/Perfumetrader tracking-ready flags do not waive per-SKU/stock/price/image
  evidence. No merchant offers activated.
- Render connector requires explicit TNCommerce workspace confirmation. The
  public storefront returned HTTP 200; that does not establish deploy SHA.

## Verification

Python content review regression tests; SQL audio matrix and real owner-review
trigger/revision replay on disposable PGlite/Postgres. Dedicated CI PostgreSQL
tests load the new migration and include public-audio-verification rejection.
SQL fixtures contain test claims only and never publish. Internal function
execution remains restricted to service_role; no RLS or browser access widened.

Sources:
https://help.metricool.com/how-to-add-audio-to-your-instagram-reels-from-metricool-2o2ks
https://help.metricool.com/instagram-posting-errors-troubleshooting-fkhpc
