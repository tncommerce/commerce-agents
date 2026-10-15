# DUFYND BUSINESS EXECUTION-20 — release handoff, 14 October 2026

Base: SITE-13 PR #788, `5f858bc9abec5b5d725a641d4861f5bf6bcbb44c`.
Isolated branch: `dufynd-business-execution-20-20261014`. No protected merge or deployment authorized.

## Implemented delta

- Shared offer cards show the exact variant before the price, use readable 13px price/dispatch explanations and 12px verification timestamps, and expose known item/shipping breakdown on all product pages (previously Rabanne-focused only). Unknown shipping remains explicitly unknown; no price, ordering, freshness, merchant URL, session or attribution algorithm was changed.
- All merchant actions, including pending-session placeholders, have a 48px minimum target. New-tab behavior is visible and named for screen readers. Affiliate labels remain beside each merchant. Purchase/return responsibility and time-sensitive prices are explained in ordinary text; detailed ranking is available in a native disclosure.
- Privacy copy now describes the actual SITE-13 sessionStorage analytics identity and existing acquisition storage, internal URL continuation and affiliate event references. The former claim of no analytics identity in sessionStorage was false for #788. This factual correction is a draft for legal review, not proof of legal compliance. Consent requirements, legal basis, retention and provider agreements remain review items; no consent logic changed.
- Scoped the existing private-photo stage selector with `:has(.sourcePhoto)` to satisfy CSS Module purity. This fixes an actual Webpack compile failure; the source asset, rights gates and matching review stage dimensions are unchanged.

## Verification actually performed

- `node scripts/test-offer-presentation.mjs`: 9 isolated React SSR cases PASS. Focused/common cards; known/unknown/zero shipping; pending session; non-partner link; loading/error/empty. Values and generated link parameters retained; no network requests, no merchant clicks.
- `next build --webpack`: PASS; TypeScript and 105 static pages generated. No broad unchanged prebuild test suite rerun.
- `tsc --noEmit`: PASS; `git diff --check`: PASS.
- Existing #788 and #774 successful CI is reused as historical evidence, not represented as a run on this new delta.

## Browser release gate — still OPEN

The required new before/after QA at 320, 390 and 1440px was NOT completed. Work Cloud Browser rejected the local-export `file:` navigation under its URL policy. No workaround, alternate browser execution or production analytics traffic was used. Existing SITE-13 screenshots are baseline evidence only, not BUSINESS-20 results. A successful compile or SSR render does not prove layout, contrast, tap behavior or image loading.

Before release, use a supported authorized isolated preview with API/analytics fully mocked and external requests blocked. Inspect `/duft`, Rabanne and the existing licensed Lancôme page at 320/390/1440px. Capture baseline #788 and this commit. Check no horizontal overflow, complete prices/variants, 48px merchant actions, keyboard focus and open ranking disclosure; inspect loading/error/empty and unknown shipping. Do not activate merchant anchors. Preserve screenshots and exact commit/fixture hashes. No changes to paid services or new public deployment are approved.

## Actual external dependencies

- PHOTO_RIGHTS_OR_VISUAL_HOLD: no exact authorized Perfumetrader/Awin Rabanne EDT100 asset + current image-specific terms. Awin tab independently shows sign-in, so no fresh authenticated media inspection was possible. Commons fallback remains rejected by PHOTO-14; merchant-bound review photos are not transferable. Existing Lancôme original remains rights-cleared; no asset added/replaced.
- Rabanne verifier is fresh: 12 October 19:58 UTC, expires 15 October 19:58 UTC. This is existing verification evidence, not a new merchant request or transaction.
- Revenue UNKNOWN: an authorized original current Awin all-status export is still required by the existing offline reconciler. No new dashboard/reconciler/scheduler. The five Instagram sessions around 14 October 16:54 Berlin remain origin-unknown and are not a conversion or uplift claim.
- Observer requires owner reauthentication through the existing private broker (`gmail.metadata`); prior refresh failed revoked/invalid_grant. All 11 existing cron jobs retained. No new pilot, schedule, service configuration or credentials changed.

## Integration sequence

1. #784 independent campaign-link correction (do not duplicate).
2. Separate isolated integration package resolves #774 vs current #780/scentai-mvp while preserving the released brand directory and both QA gate families. Owner review first; existing protected branches remain untouched.
3. #774 → #788 → this BUSINESS-20 delta; coordinate privacy correction/review with #788 rather than releasing misleading copy in between. Fresh combined-state browser QA required after conflict integration.
4. #783 → #785 publishing protection remains a separate migration/adapter/binding approval path.
5. #775 → #786 → #787 pilot evidence stays separate; no rearming.

Next economic phase: clear the website integration/privacy/browser gates and release only with owner GO, while obtaining the existing Awin revenue export and exact authorized Rabanne photograph. Rabanne remains the best-evidenced affiliate path; other catalog affiliate URLs alone do not prove fresh, correctly sized offers.
