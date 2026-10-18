# DUFYND — RC1 First Money Release / WORK45

**Stand:** 18. Oktober 2026. **Status:** DRAFT, NOT LIVE; no merge/deploy approval.
**Protected base:** `2868882d337244a7d4f0c3ac8b7c51ef9f9d5e7e`.
**Starting release #803:** `74d9cb4db92cd245f3636831d2f7784fd447b3c2`.
**Search source #799:** `a6c0a63cabc9e8d259558f9c8c5044520c010d39`.

## Intended user-facing delta

1. Catalog cards say **Duftprofil entdecken**. Only the exact released
   `SC-RABANNE-1-MILLION-EDT-100` card adds the internal, accessible
   **Händlerangebote prüfen** link to `/duft/rabanne-1-million#angebote`.
2. The existing shared search accepts **One Million**, **onemillion** and
   **1million**, in addition to the previous correct spellings. These aliases
   are restricted to brand Rabanne and the complete name 1 Million. Existing
   explicit size/concentration filters are unchanged. Lucky, Elixir, other
   brands, wrong sizes and wrong concentrations must not resolve to RC1.
3. The unapproved abstract 1200×630 OG creative is **excluded**. Independent
   visual inspection rejected its medal/pedestal motif as insufficient perfume
   identity. No replacement generation. RC1 uses text-only summary metadata
   until an authorized original photo is available. Existing verified original
   photographs still take precedence; Product JSON-LD image rights gates remain.

## Minimal source transfer and creative separation

Only `fragranceSearchIdentity.ts` and its existing unit tests are copied from
exact #799. Its alias browser cases are adapted onto the existing #803 suite;
#803 save/compare, CTA layout and complete URL assertions stay enabled.
No hero, homepage, shader, image research asset or other #799 runtime code is
imported. Production detail component and package scripts match the protected
base again after removal of the rejected creative and generator.

Dynamic RC1/unrelated-product/licensed-photo metadata cases now live in the
already active `test-fragrance-metadata.mjs`, preserving the original indexing
cases. Exported DOM checks explicitly require no RC1 OG/Twitter image, truthful
exact title and a `summary` card. Python guards retain Product image restrictions
and prohibit reintroducing this unapproved creative. This is an intentional
scope removal, not a test bypass or premium-creative approval.

## New-commit verification contract

Full routine CI is mandatory on this new release commit. The previous passes
(803: 39074257623; 799: 39104846696) are provenance, not proof for this revision.
Record exact SHA, run ID, jobs, original artifact ID/hash and independent visual
verdict in the PR and handoff only after completion.

New browser matrix: **320 / 390 / 768 / 1440 px**, Instagram and TikTok. Each
platform has granted and denied cases; touch is actually exercised below1024,
keyboard on1440; denied cases use reduced motion. APIs use isolated fixtures.

- Social direct search tests all aliases and exact RC1 identity.
- A second actual route follows `/start` -> **Katalog entdecken** -> `/duft`,
  fills all aliases and activates the exact internal offer CTA to `#angebote`.
  No campaign values are reinjected between those hops.
- Granted navigation retains source, campaign, content and one independent
  analytics session; destination events must carry the same attribution.
- Denied navigation emits no optional analytics and strips optional URL fields.
- Wrong50ml/EDP/Lucky/Elixir queries cannot show the RC1 offer CTA.
- Empty offers display the existing honest fallback; no price, availability or
  merchant destination is invented. Existing CI tests cover available-offer
  presentation, consent and affiliate boundaries. No real merchant clickouts.
- Capture `alias45-{width}-{source}-{social,catalog,offers}.png`; visually inspect
  originals separately from automated assertions. No physical-device QA claim.

## Strict isolation and remaining gates

No Jarvis #800/#801/#802, SQL migrations, activation, paid tools, social posts,
merchant data, prices, affiliate destinations or protected branch changes.
No new remote branch/PR. The release remains Draft after successful checks.
Production merge/deploy and social publishing remain **OWNER-GATED**.

No new hero work: rejected CGI/photo studies remain rejected. A commercially
usable original with unmistakable perfume identity and strong mobile framing
is still required before any further hero implementation.

## Business measurement

Keep Social views, website sessions, exact product views, offer views, clickouts
and verified commissions separate. Test fixtures and CI do not establish traffic,
sales or revenue. Use the existing content/link funnel; no duplicate routine.
