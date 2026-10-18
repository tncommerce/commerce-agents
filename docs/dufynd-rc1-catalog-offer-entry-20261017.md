# DUFYND RESET40 — offer-scoped catalog entry (DRAFT)

**Purpose:** A user viewing the DUFYND fragrance catalog should not see
`Duftprofil & Angebote ansehen` on every fragrance when the only released,
independently checked affiliate RC1 is Rabanne 1 Million Eau de Toilette 100 ml.
This small disclosure/conversion improvement is independent of the unapproved
premium Hero and does **not** infer new live offers or sales.

- Existing fragrance card image/body still links to its exact fragrance profile.
- Only exact product ID `SC-RABANNE-1-MILLION-EDT-100` exposes one separate,
  accessible 44px+ internal shortcut to `/duft/rabanne-1-million#angebote`.
  It says **Händlerangebote prüfen** — no price, stock or guaranteed availability.
- Other product cards say only **Duftprofil entdecken**, not that an offer exists.
- No partner-link href, merchant product, buy URL, pricing, indexing, photo right,
  analytics policy, event instrumentation, cookie choice or catalog ranking changes.
  `AcquisitionInternalLink` retains campaign attribution.
- Existing search and quick paths remain. This is a narrow **catalog** entry
  improvement, not a repeat of the earlier **homepage** RC1 quick path.

**Regression scope:** Real Chromium catalog search at widths 390 / 1440,
including a no-offer Libre profile, exactly one RC1 shortcut, exact internal
route and hash, campaign `src` / `cmp` continuity after click, navigation
to real `#angebote`, no external clickout. The existing visual QA screenshots
include a new `conversion-search-*-rc1-catalog.png` capture. Accept this
only if the card remains legible and accessible at both widths.

**Release:** development PR #799 only. CI success is not evidence of uplift.
Conversion after launch requires real attributable sessions, offer views,
merchant clickouts and eventually confirmed partner commissions. Separate
Owner merge/deploy GO mandatory. No additional paid services or content.

## RESET41 — evidence-led responsive CTA repair (pending exact CI)

Original screenshots from [RESET40 CI #39069002565](https://github.com/tncommerce/commerce-agents/actions/runs/39069002565)
(artifact `dufynd-visual-qa-799`, ID 12115011508) independently exposed a
problem **not caught by the successful technical run**: at both 390 and 1440 px
the arrow on the new catalog offer button appeared on a second line. The
desktop photo-pending archive card also auto-placed its Save/Compare controls
in the wrong grid column.

Root cause: the legacy `.dufynd-catalog-card > a` selector set
`display:flex;flex-direction:column;flex:1` for every direct child anchor,
including the new CTA, and the 1024px+ non-photo archive grid had no explicit
positions for its third direct child. The fix wraps *only the exact RC1*
action in its own container, makes the CTA a guaranteed horizontal label
and arrow, and explicitly places the CTA and Save/Compare controls in the
right column on desktop. No URL, consent, merchant, price or product identity
changed. The existing responsive browser QA now fails if the arrow wraps,
the button becomes oversized or the desktop actions leave the CTA column.

**This fix requires a NEW exact-HEAD responsive CI/artifact review; a prior
green run is not visual approval.**
