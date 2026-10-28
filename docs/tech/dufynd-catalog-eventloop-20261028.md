# DUFYND catalog evidence and API liveness — 28 October 2026

Base: `89aae8925e606caa33f8f7dafa3edbeafab32c3c`.

## Verified defect

The public catalog routes called synchronous `MockRetail.customer_product`
callbacks directly on the ASGI event loop. These callbacks decorate products
with merchant prices through `MerchantOfferStore.offers_for`; its evidence
loader can wait on synchronous Supabase I/O. A slow evidence read therefore
prevented an unrelated `/api/health` request from running.

The merchant-offer route already offloaded its main evidence read, but its
`_live_dufynd_offer_product` scope check first called `customer_product` on the
event loop. The older concurrency test replaced this scope check with `True`
and did not cover the actual HTTP path.

## Change

- DUFYND opts into the existing Starlette worker pool for the complete catalog
  list/detail callback and payload preparation. The shared host's default
  remains unchanged because other demo backends mutate inventory during reads.
- Merchant scope validation reads only the local raw catalog and the existing
  customer-visibility predicate. Product prefix, fragrance category, stock and
  blocked-product checks remain mandatory. The subsequent offer evidence and
  clickout eligibility checks remain in place.
- `/api/health` keeps its existing response and liveness meaning. This change
  does not add a provider probe or claim successful business work.

## Verification

New test file: `tests/test_dufynd_catalog_eventloop.py`.

Against the unchanged base, four tests failed and one passed: the real catalog
list, product-detail and merchant-offer HTTP requests each blocked health, and
the scope guard performed forbidden evidence I/O. The same five tests pass
with this patch. A thread event holds the synchronous evidence stub until
health responds; the test does not infer responsiveness from a mocked guard or
source text. No merchant request, clickout, model call or analytics event is
made.

Final focused run: **22 passed, 124 deselected** (Python 3.12). This covers the
five new cases, existing offer nonblocking/scope/price-source checks, DUFYND's
health payload, and health plus slash-containing product IDs across all four
consumers of the shared storefront host. Ruff check, Ruff format check and
`git diff --check` pass. Existing Starlette TestClient deprecation warnings
remain unrelated to this change. Standard Python CI discovers the new tests
without workflow edits; no remote CI was triggered for this local patch.

The local network sandbox blocked even a minimal `asyncio.to_thread` wakeup.
The focused tests therefore ran outside that sandbox, with offer reads stubbed
and no external calls. A minimal thread-wakeup self-test confirmed this was a
test-environment limitation.

## Remaining scope

This isolates evidence latency from the ASGI event loop; it does not change
provider timeouts, cache freshness, offer ordering or total catalog-read
latency. Worker-pool capacity stays at the existing framework limit. No Render
configuration, deployment, resource, spend setting or health-check path is
changed by this patch.
