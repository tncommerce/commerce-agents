# Rabanne 1 Million EDT 100 ml — final landing quality

Development only: PR #774, branch `dufynd-core-product-nightshift-20261010`.
Baseline `7fbb008be6c54457f8baf5725ab1136a0d3d10b2`, successful CI `38233905793`, artifact `11739444868`.

## Confirmed problems and scoped corrections

- The 67.95 EUR market reference dated 2026-09-27 appeared in both the header and footer. Both references are now omitted for this product. Visible purchase prices come exclusively from the existing freshness-filtered merchant-offers endpoint; no replacement price is hardcoded.
- A single offer had a long sorting explanation above the purchase card, repeated in the disclosure below. Its introduction is shortened; multiple-offer ranking explanations and the affiliate disclosure remain. Article price and shipping are shown alongside the known total without double-counting shipping text.
- The failed/empty offer panel previously contained a prominent external manufacturer link. On this first-money landing it now clearly states temporary API unavailability or no eligible offer, with an internal recovery path. Retry, hero and merchant CTAs have 44 px minimum touch targets.

The presentation option is passed only by the existing Rabanne detail page. Other product pages, catalog data, offer records, images and production services are unchanged.

## Read-only real offer evidence

A GET on 2026-10-12 at 10:37:38 UTC to `https://scentai-api-kxhe.onrender.com/api/merchant-offers/SC-RABANNE-1-MILLION-EDT-100` returned HTTP 200:

- Perfumetrader offer `perfumetrader-rabanne-1-million-edt-100`, merchant product ID `16978322`;
- 100 ml, Eau de Toilette, in stock, affiliate link enabled in the existing API response;
- 71.90 EUR article + 4.99 EUR German shipping = 76.89 EUR total;
- record timestamp **2026-10-10T19:56:00.217168+00:00** (not relabelled as an October 12 merchant revalidation);
- response SHA256 `a073700b4983e0e133e985555f6d053e7742ee930583b284da2603bb1540a4f7`.

These are time-bound observations. The existing backend eligibility filter, including freshness and stock, remains authoritative. No merchant page or redirect was opened.

## Browser evidence and tests

The existing `social-product-entry-qa.mjs` retains its four source/width checks and now also asserts that the historical price is absent and primary tap targets are at least 44 px. It still uses the explicit artificial 90 + 5 EUR fixture, isolated from all public views.

The additional landing-state function uses a local storefront and intercepts every API. It permits exactly one read-only GET of the public offer endpoint, with credentials-free headers, no redirects, no retries and a 7-second timeout (below the frontend's existing 8-second deadline). It passes that original response into the existing frontend fetch path. The second viewport reuses the identical captured response. It never calls a merchant/affiliate endpoint. A failed API capture is recorded as unavailable, not replaced with a synthetic successful offer.

Deterministic error, empty and retry tests are separate. Retry uses the labelled artificial fixture; it verifies that campaign parameters survive and that no obsolete error remains. All analytics are intercepted and must be marked internal QA. Test code and artificial prices are not imported into the public application.

CI artifacts at 390 and 1440 px:

- `social-product-fixture-*.png`: same artificial successful data as the baseline, for like-for-like comparison;
- `rabanne-1-million-*.png` / `landing-error-*.png`: failed-offer state;
- `landing-live-offer-*.png` and `*-section.png`: actual public API response rendered in the isolated browser;
- `landing-empty-*.png`: no eligible offer;
- `landing-live-offer-evidence.json`: original response, retrieval time, hash and explicit availability status;
- `report.json`: deterministic checks and separately labelled live evidence.

## Remaining release gates

No public release is authorized. A suitable photo for this Perfumetrader context is still absent; top-Parfümerie's private photo approval is not transferable. No new image, merchant activation, social change, revenue claim or network-report import is part of this change. Final visual assessment must use the CI images and remain distinct from an owner design/release decision.
