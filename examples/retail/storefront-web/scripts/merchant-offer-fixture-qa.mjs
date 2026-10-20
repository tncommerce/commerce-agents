// QA-only response identity: derive it from the exact intercepted offer request.
export function offerFixtureProductId(route) {
  const { pathname } = new URL(route.request().url());
  const match = /^\/api\/merchant-offers\/([^/]+)$/.exec(pathname);
  if (!match) throw new Error(`Unexpected merchant-offer fixture path: ${pathname}`);
  const productId = decodeURIComponent(match[1]);
  if (!productId.trim() || productId.includes("/")) {
    throw new Error(`Invalid merchant-offer fixture product ID: ${pathname}`);
  }
  return productId;
}

export function emptyOfferFixture(route) {
  return {
    product_id: offerFixtureProductId(route),
    offers: [],
    best_offer_id: null,
    affiliate_disclosure: "Isolated QA fixture only",
  };
}
