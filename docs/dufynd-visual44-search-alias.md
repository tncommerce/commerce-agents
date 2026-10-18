# Visual44: exact RC1 search spelling

The existing social post uses `#onemillion`, but the public search identity only
contained `1 Million`. `One Million`, `onemillion` and `1million` returned no
match despite the exact released Rabanne Eau de Toilette 100 ml being present.

The shared search identity now includes those spellings only when the normalized
brand is `rabanne` and the complete normalized product name is `1 million`.
The existing size and concentration filters are unchanged. No fuzzy matching,
product publication, price, merchant, affiliate destination or analytics contract
changes. Both social entry and catalogue search consume the same identity.

## Verification

`test-fragrance-search-identity.mjs` checks canonical and alternative spellings
against competing brands, Lucky, Elixir, 50 ml and EDP fixtures. Existing cases
remain. The production storefront build passes its existing pre/postbuild gates.

`verifyProductNameAliases` extends the existing conversion-search browser suite.
It checks social search, touch/keyboard navigation, catalogue results and the
internal exact offer anchor at 320, 390, 768 and 1440 pixels. Local Chromium
134.0.6998.35 passed all four cases. The 320/768 cases use reduced motion and deny
measurement, with zero analytics requests. Granted 390/1440 cases preserve source
and campaign attribution. Wrong size, concentration and flanker queries remain
empty. Every API is an isolated fixture; no merchant clickout occurs.

Local screenshots: `alias44-{320,390,768,1440}-{social,catalog,offers}.png`.
The regular PR CI invokes this function through `verifyConversionSearch`; its
exact commit/run result is recorded in the PR, without inferring a CI pass from
the local result. Tests establish navigation correctness, not traffic or revenue.

## Visual decision

The previous hero was inspected from original PR #799 CI 39070518141 artifact
12114972293, source `ad6e2a945312da376a6f8ad47b64216c47cfc18a`.
One new photographic direction, **Licht / Essenz**, was composed and captured in
a browser at all four requested widths. It uses the unbranded Alesia Kozik photo
https://www.pexels.com/photo/clear-bottle-on-top-of-a-mirror-7796312/ under the
Pexels photo license. The still improves real light and material depth, but the
pump bottle remains ambiguous between perfume and cosmetic oil. Independent
review rejected it, especially at mobile widths. It is not integrated and no
9.5/10 claim is made. No further CGI or cosmetic iterations were performed.

The remaining visual dependency is a commercially usable photographic master
with immediate perfume identity and convincing desktop/mobile crops. The full
source audit and browser stills are retained in the Visual44 handoff. The exact
photo provenance, licensing restrictions and other rejected candidates are
documented there. No third-party photo is added to this repository.

PR #803 remains separate and unchanged. Its 1200x630 editorial OG generator was
reproduced from exact source and visually inspected. Its CI archive does not
contain the original OG PNG; differing local font substitution prevents a
byte-identical CI-image claim. The reproduction is a usable textual fallback,
not a licensed product-photo substitute. No OG correction was made.

## Boundaries

Development stays in existing draft PR #799. Production, PR #803 and Jarvis
PR #800 are untouched. Merge, deployment and publishing remain owner-gated.
No production SQL, paid generation, extra service or new branch/PR is required.
