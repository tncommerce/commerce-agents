// Bind the offer-boundary browser review to exact, non-secret test sources.
// Uses the existing .visual-qa artifact; no network, process execution or upload.
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';

if (process.env.GITHUB_ACTIONS === 'true') {
  const paths = [
    'dufynd-visual-qa.mjs',
    'conversion-search-qa.mjs',
    'offer-recovery-qa.mjs',
    'site13-funnel-qa.mjs',
    'social-product-entry-qa.mjs',
  ];
  const sources = [];
  for (const filename of paths) {
    const bytes = await readFile(new URL(filename, import.meta.url));
    sources.push({ filename, bytes: bytes.length,
      sha256: createHash('sha256').update(bytes).digest('hex'),
      source: bytes.toString('utf8') });
  }
  const directory = new URL('../.visual-qa/', import.meta.url);
  await mkdir(directory, { recursive: true });
  await writeFile(new URL('offer-fixture-source-evidence.json', directory),
    JSON.stringify({ schema: 1, checkout_sha: process.env.GITHUB_SHA || null,
      run_id: process.env.GITHUB_RUN_ID || null,
      scope: 'Fixed public QA sources only; not runtime data or credentials', sources }, null, 2));
  console.log('Offer fixture source evidence saved for existing visual-QA artifact.');
}
