import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import vm from "node:vm";

const require = createRequire(import.meta.url);
const ts = require("typescript");
const code = readFileSync(new URL("../lib/duftduell.ts", import.meta.url), "utf8");
const js = ts.transpileModule(code, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
const mod = { exports: {} };
vm.runInNewContext(js, { module: mod, exports: mod.exports });
const { DUEL_ROUNDS, DUEL_OUTCOMES, getDuelOutcome, getDuelAdvisorPrompt } = mod.exports;

assert.equal(DUEL_ROUNDS.length, 4);
assert.equal(new Set(DUEL_ROUNDS.map((r) => r.id)).size, 4);
for (const round of DUEL_ROUNDS) {
  assert.equal(round.options.length, 2);
  assert.notEqual(round.options[0].label, round.options[1].label);
  for (const option of round.options) {
    assert.ok(option.label.length > 0 && option.detail.length > 0);
    assert.ok(Number.isFinite(option.warmth) && Number.isFinite(option.presence));
  }
}
assert.equal(getDuelOutcome([]), null);
assert.equal(getDuelOutcome(["a", "b"]), null);
assert.equal(getDuelOutcome(["a", "b", "b", "invalid"]), null);
const found = new Set();
for (let mask = 0; mask < 16; mask++) {
  const picks = Array.from({ length: 4 }, (_, i) => mask & (1 << i) ? "b" : "a");
  const output = getDuelOutcome(picks);
  assert.ok(output);
  found.add(output.id);
  assert.ok(DUEL_OUTCOMES[output.id]);
  const prompt = getDuelAdvisorPrompt(picks);
  assert.ok(prompt.includes("Budget") && prompt.includes("Katalog"));
  assert.ok(prompt.length < 2400, "Advisor prompt must remain within existing bounded storage contract");
  assert.equal(getDuelOutcome(picks)?.id, output.id, "Deterministic selection");
}
assert.deepEqual([...found].sort(), ["afterdark", "clean", "electric", "sunset"]);
const page = readFileSync(new URL("../app/duftduell/page.tsx", import.meta.url), "utf8");
assert.ok(page.includes('AcquisitionAnalytics source="duftduell"'));
const client = readFileSync(new URL("../components/DuftduellExperience.tsx", import.meta.url), "utf8");
assert.ok(client.includes("GuidedAdvisorLink") && client.includes("getDuelAdvisorPrompt"));
assert.ok(client.includes("AcquisitionInternalLink"));
assert.ok(!client.includes("merchant_clickout") && !client.includes("localStorage"));
console.log("DUFYND Duft-Duell: 4 rounds, 16 paths, 4 outcomes, bounded advisor handoff, attribution PASS");
