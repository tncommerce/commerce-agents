// Preserve the seven existing native privacy scenarios unchanged, then check
// the mounted-product grant/withdrawal lifecycle separately. No global consent seed.
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { verifyMeasurementBrowser as verifyCore } from './measurement-browser-core-qa.mjs';
import { verifyLateMeasurementGrant } from './measurement-late-grant-qa.mjs';

export async function verifyMeasurementBrowser(browser, baseUrl, outputDir) {
  const out = path.join(outputDir, 'consent26');
  await mkdir(out, {recursive:true});
  const results = [];
  try {
    results.push(...await verifyCore(browser, baseUrl, outputDir));
    results.push(...await verifyLateMeasurementGrant(browser, baseUrl, outputDir));
    await writeFile(path.join(out, 'report.json'), JSON.stringify({
      status:'PASS', cases:results.length, results,
      realMerchantClicks:0, externalRequests:0,
    }, null, 2));
    return results;
  } catch (error) {
    // Never leave the earlier seven-scenario PASS looking like full acceptance.
    await writeFile(path.join(out, 'report.json'), JSON.stringify({
      status:'FAIL', completedCases:results.length, results,
      error:String(error), scope:'Native consent and mounted-product lifecycle',
    }, null, 2));
    throw error;
  }
}
