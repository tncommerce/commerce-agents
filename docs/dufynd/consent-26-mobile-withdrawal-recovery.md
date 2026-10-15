# CONSENT-26: keep mobile withdrawal controls reachable

15 October 2026. Parent `9f5e4962c4be85adcbe4eb99fd31e6ed95b75ec6`.
Existing development branch `dufynd-consent-26-20261015`, draft PR #794.
No release or complete consent-integration PASS is claimed.

## Exact observed failure

Parent CI #38754614705 completed with six required jobs successful, including
both Python versions and the storefront build. Its browser job failed.
Artifact #11983226196 (1,409,145 bytes) was downloaded and ZIP CRC verified.
SHA256: `de6299fbd0a54b0bcd64e47b6515ab86b3b360999f38659dc11b23968fe5d71e`.

The combined `consent26/report.json` is FAIL, with the seven original native
consent scenarios completed successfully. The subsequent late-grant scenario
fails on an ordinary click of `Analyse widerrufen`: the fixed mobile offer bar
intercepts the pointer at the privacy footer. The report's false overall result
is retained; seven successful subcases are not overall acceptance. The broader
browser suite was not reached in this run.

This is a real interface conflict, not a reason to force-click or bypass consent.

## Bounded source correction

MobileOfferBar now observes the existing server-rendered measurement-choice
region alongside the hero CTA and merchant-offer section. If that privacy region
is even partially visible, the fixed purchase shortcut is not rendered. Scrolling
back to the product content restores it when neither original offer entry is
visible. The existing scroll/resize fallback applies the same rule and cleans up
listeners. No extra scheduler, consent implementation or overlay was introduced.

Component source parent blob: `c30c4a17489b55fca918acb3d8fcbfd22fe09e54`.
Corrected component blob: `7264bcda49daa27ca9eb653f5a1c35eb14fb3149`.
The entire source was matched to its original Git blob before local editing.
No product image, price, attribution field, consent gate, API or CSS change.

## Tests actually run locally before committing

`node scripts/test-mobile-offer-privacy.mjs`: **32 assertions PASS**. The test
compiles the actual component with TypeScript and invokes its actual effect with
isolated geometry/React-hook fixtures. It covers visible and partly visible
privacy controls, restoration, original CTA and offers, resize, observer and
non-observer fallback, missing optional elements and lifecycle cleanup.
The identical test against the exact parent component FAILS at the first privacy
visibility assertion. Test blob: `7b0c21c7bb245581568f9bad174a68a2f6c946ec`.
The test is added to the existing prebuild; no new dependency or workflow.

An additional local Chromium DOM fixture executed that same transpiled component
effect at 320, 390, 768 and 1440 pixels, once per source version: **8 cases PASS**.
Both phone parent controls reproduced the obstruction. Corrected controls were
unobstructed, accepted a normal pointer click and restored the purchase shortcut
after leaving the footer. No network requests or merchant navigation occurred.
This geometry fixture does NOT execute the full React/Next website, and the
fixture click is NOT evidence of production consent revocation.

## Integration acceptance still pending

All existing native consent/late-grant and full-site browser tests are unchanged.
The previously failing ordinary withdrawal click must now pass there too.
The standard exact-head CI remains the final integration check, not the local
fixtures. No existing check, timeout, consent choice or failure is removed.
Other legacy attribution fixtures and the copied-grant-URL server limitation,
retention/deletion, provider agreements and exact Rabanne image rights remain
separate open work. No new email, paid service, Nightshift activation, protected
merge, deployment or live database mutation is performed by this correction.
