import assert from 'node:assert/strict';
import { publicCount } from './public-catalog-summary.mjs';
import { verifyBrandDiscovery } from './brand-discovery-qa.mjs';
import { chromium } from 'playwright';
import { writeFileSync, mkdirSync } from 'node:fs';

const base = process.env.QA_BASE_URL || 'http://127.0.0.1:3013';
const out = process.env.QA_OUTPUT || '/tmp/dufynd-brand-qa';
mkdirSync(out, { recursive: true });
const browser = await chromium.launch();
let report;
try {
  // Reuse the released text-only brand route contract at all prior review widths.
  // Includes every brand/product, real navigation, noindex, overflow and page errors.
  report = await verifyBrandDiscovery(browser, base, out, [320, 390, 768, 1440]);
  for (const check of report) assert.equal(check.products, publicCount);
} finally {
  await browser.close();
}
writeFileSync(`${out}/brands-qa.json`, JSON.stringify(report, null, 2));
console.log(JSON.stringify(report));
