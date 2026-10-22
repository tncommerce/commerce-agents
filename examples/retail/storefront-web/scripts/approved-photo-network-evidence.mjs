/**
 * Passive diagnostic for EXACT registered original-photo requests in browser QA.
 * No requests, retries, URL changes, browser routing, downloaded assets or
 * synthetic replacements are made by this module. A missing original stays FAIL.
 */
import { readFileSync } from "node:fs";

const PHOTO_REGISTRY = JSON.parse(
  readFileSync(new URL("../lib/generated/original-photos.json", import.meta.url), "utf8"),
);

export function watchApprovedPhotoRequests(page, registry = PHOTO_REGISTRY) {
  const known = new Map(registry.map((item) => [item.url, item]));
  const events = [];
  const record = (url, kind, details = {}) => {
    const item = known.get(url);
    if (!item) return;
    events.push({ product_id: item.product_id, kind, ...details });
    if (events.length > 48) events.shift();
  };

  page.on("request", (request) => {
    record(request.url(), "requested", { resource_type: request.resourceType() });
  });
  page.on("response", (response) => {
    record(response.url(), "http_response", {
      status: response.status(),
      content_type: response.headers()["content-type"] ?? null,
    });
  });
  page.on("requestfailed", (request) => {
    const failure = request.failure();
    record(request.url(), "network_failed", {
      error: typeof failure === "string" ? failure : failure?.errorText ?? "unknown_request_failure",
    });
  });

  return {
    snapshot(productId) {
      return events.filter((event) => !productId || event.product_id === productId);
    },
  };
}

export async function explainMissingApprovedPhoto(page, witness, productId, registry = PHOTO_REGISTRY) {
  const registered = registry.find((item) => item.product_id === productId);
  if (!registered) return { product_id: productId, registry_state: "not_approved", events: [] };

  let dom;
  try {
    dom = await page.evaluate((expectedUrl) => {
      const images = [...document.querySelectorAll("img[src]")]
        .filter((image) => image.getAttribute("src") === expectedUrl)
        .map((image) => ({
          complete: image.complete,
          natural_width: image.naturalWidth,
          natural_height: image.naturalHeight,
        }));
      return {
        matching_original_images: images,
        unavailable_fallbacks: document.querySelectorAll('[data-dufynd-visual-state="unavailable"]').length,
        missing_source_holds: document.querySelectorAll('[data-dufynd-visual-state="missing"]').length,
      };
    }, registered.url);
  } catch (error) {
    dom = { inspection_error: String(error) };
  }

  return {
    product_id: productId,
    approved_url: registered.url,
    rights_basis_id: registered.rights_basis_id,
    dom,
    events: witness.snapshot(productId),
    verdict: "release_fail_until_original_image_verified",
  };
}
