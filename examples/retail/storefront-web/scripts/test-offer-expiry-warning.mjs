// Deterministic no-network early-warning regression. Uses fixed evidence timestamps.
// No browser, OAuth, provider call, analytics, clickout or URL navigation.
import assert from "node:assert/strict";
import { upcomingAffiliateExpirations } from "./offer-expiry-warning.mjs";

const HOUR_MS = 3_600_000;
const sourceOffers = [
  {offer_id: "notino-pdm-delina-edp-75", product_id: "SC-PDM-DELINA-EDP-75",
    last_updated_at: "2026-10-18T09:38:01.133Z", affiliate_url: "https://www.jdoqocy.com/click-fixture"},
  {offer_id: "notino-ysl-black-opium-edp-90", product_id: "SC-YSL-BLACK-OPIUM-EDP-90",
    last_updated_at: "2026-10-18T09:38:01.134Z", affiliate_url: "https://www.jdoqocy.com/click-fixture"},
  {offer_id: "notino-ysl-libre-edp-90", product_id: "SC-YSL-LIBRE-EDP-90",
    last_updated_at: "2026-10-18T09:38:01.135Z", affiliate_url: "https://www.jdoqocy.com/click-fixture"},
];
let cases = 0;
assert.deepEqual(upcomingAffiliateExpirations([], Date.parse("2026-10-19T08:00:00Z")), []); cases++;
assert.equal(upcomingAffiliateExpirations(sourceOffers, Date.parse("2026-10-20T09:00:00Z")).length, 0); cases++;
const soon = upcomingAffiliateExpirations(sourceOffers, Date.parse("2026-10-20T10:00:00Z"));
assert.deepEqual(soon.map(x => x.offer_id), sourceOffers.map(x => x.offer_id));
assert(soon.every(x => x.remaining_hours > 23 && x.remaining_hours < 24));
assert(soon.every(x => x.expires_at.startsWith("2026-10-21T09:38:01."))); cases++;
assert.equal(upcomingAffiliateExpirations(sourceOffers, Date.parse("2026-10-21T10:00:00Z")).length, 0); cases++;
const precise = sourceOffers[0];
const expiryMs = Date.parse(precise.last_updated_at) + 72 * HOUR_MS;
assert.equal(upcomingAffiliateExpirations([precise], expiryMs - 24 * HOUR_MS).length, 1);
assert.equal(upcomingAffiliateExpirations([precise], expiryMs - 24 * HOUR_MS - 1).length, 0);
assert.equal(upcomingAffiliateExpirations([precise], expiryMs).length, 1);
assert.equal(upcomingAffiliateExpirations([precise], expiryMs + 1).length, 0); cases++;
assert.equal(upcomingAffiliateExpirations([
  {...precise, affiliate_url: null},
  {...precise, last_updated_at: "not-a-date"},
  {...precise, product_id: "../../invalid"},
  {...precise, offer_id: ""},
], expiryMs - HOUR_MS).length, 0); cases++;
assert.throws(() => upcomingAffiliateExpirations(sourceOffers, NaN), RangeError);
assert.throws(() => upcomingAffiliateExpirations(sourceOffers, expiryMs, 73), RangeError); cases++;
console.log(JSON.stringify({status: "PASS", cases, networkRequests: 0, merchantClicks: 0,
  note: "Candidate offer expiry warning only; no live supplier evidence refreshed"}));
