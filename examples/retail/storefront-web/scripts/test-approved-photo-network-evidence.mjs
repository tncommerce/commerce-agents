import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import { watchApprovedPhotoRequests, explainMissingApprovedPhoto } from "./approved-photo-network-evidence.mjs";

const registry = [
  { product_id: "SC-YSL-LIBRE-EDP-90", url: "https://img.example.test/approved.png", rights_basis_id: "owner-approved" },
];
class FakePage extends EventEmitter {
  async evaluate(callback, source) {
    assert.equal(source, registry[0].url);
    assert.equal(typeof callback, "function");
    return { matching_original_images: [], unavailable_fallbacks: 1, missing_source_holds: 0 };
  }
}
const page = new FakePage();
const trace = watchApprovedPhotoRequests(page, registry);
const url = registry[0].url;
page.emit("request", { url: () => "https://unrelated.example/clickout", resourceType: () => "document" });
page.emit("response", { url: () => url, status: () => 403, headers: () => ({ "content-type": "text/html" }) });
page.emit("requestfailed", { url: () => url, failure: () => ({ errorText: "net::ERR_NAME_NOT_RESOLVED" }) });
assert.deepEqual(trace.snapshot("SC-YSL-LIBRE-EDP-90").map((event) => event.kind), ["http_response", "network_failed"]);
const result = await explainMissingApprovedPhoto(page, trace, "SC-YSL-LIBRE-EDP-90", registry);
assert.equal(result.dom.unavailable_fallbacks, 1);
assert.equal(result.rights_basis_id, "owner-approved");
assert.equal(result.verdict, "release_fail_until_original_image_verified");
assert.equal(result.events[0].status, 403);
assert.equal(result.events[1].error, "net::ERR_NAME_NOT_RESOLVED");
const unknown = await explainMissingApprovedPhoto(page, trace, "NOT-APPROVED", registry);
assert.equal(unknown.registry_state, "not_approved");
assert.deepEqual(unknown.events, []);
for (let i = 0; i < 100; i++) {
  page.emit("request", { url: () => url, resourceType: () => "image" });
}
assert.equal(trace.snapshot().length, 48, "Bounded diagnostic evidence must not grow indefinitely");
console.log("Approved-photo passive evidence: 403, DNS failure, honest fallback, unknown-source guard, bounded capture PASS");
