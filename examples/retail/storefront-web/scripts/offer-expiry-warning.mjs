// Pure, offline-first readiness warning. Never verifies or rewrites merchant data.
// Caller supplies only already-eligible affiliate offers; the 72-hour customer gate
// remains in merchant_offers.py and in check-launch-readiness.mjs.
const HOUR_MS = 3_600_000;

export function upcomingAffiliateExpirations(eligibleAffiliateOffers, nowMs, warningHours = 24, maxAgeHours = 72) {
  if (!Array.isArray(eligibleAffiliateOffers)) throw new TypeError("Expected eligible affiliate offers");
  if (![nowMs, warningHours, maxAgeHours].every(Number.isFinite) ||
      nowMs < 0 || warningHours < 0 || maxAgeHours <= 0 || warningHours > maxAgeHours) {
    throw new RangeError("Invalid bounded expiry window");
  }

  const expiring = [];
  for (const offer of eligibleAffiliateOffers) {
    if (!offer || typeof offer !== "object" ||
        typeof offer.affiliate_url !== "string" || !offer.affiliate_url.startsWith("https://")) {
      continue;
    }
    const offerId = String(offer.offer_id || "").trim();
    const productId = String(offer.product_id || "").trim();
    if (!/^[A-Za-z0-9._:-]{1,120}$/.test(offerId) ||
        !/^[A-Za-z0-9._:-]{1,120}$/.test(productId)) continue;

    const verifiedAt = Date.parse(offer.last_updated_at || "");
    if (!Number.isFinite(verifiedAt)) continue;
    const expiresAt = verifiedAt + maxAgeHours * HOUR_MS;
    const remainingMs = expiresAt - nowMs;
    if (remainingMs < 0 || remainingMs > warningHours * HOUR_MS) continue;
    expiring.push({
      offer_id: offerId,
      product_id: productId,
      expires_at: new Date(expiresAt).toISOString(),
      remaining_hours: Math.round((remainingMs / HOUR_MS) * 10) / 10,
    });
  }
  return expiring.sort((left, right) =>
    left.expires_at.localeCompare(right.expires_at) ||
    left.offer_id.localeCompare(right.offer_id));
}
