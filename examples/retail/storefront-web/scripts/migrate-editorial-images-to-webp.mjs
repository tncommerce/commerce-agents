import fs from "node:fs/promises";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

import sharp from "sharp";

const here = path.dirname(fileURLToPath(import.meta.url));
const storefrontRoot = path.resolve(here, "..");
const repoRoot = path.resolve(storefrontRoot, "../../..");
const pilotDir = path.join(storefrontRoot, "public/products/pilot");
const archiveDir = path.resolve(storefrontRoot, "../review-assets/editorial-source-png");
const reportPath = path.join(repoRoot, "docs/dufynd-editorial-webp-migration-20260925.md");
const quality = 86;

const names = (await fs.readdir(pilotDir))
  .filter((name) => name.toLowerCase().endsWith(".png"))
  .sort((a, b) => a.localeCompare(b));

if (names.length !== 31) {
  throw new Error(
    `Expected 31 active editorial PNGs before migration, found ${names.length}`,
  );
}

await fs.mkdir(archiveDir, { recursive: true });

const replacements = new Map();
const rows = [];
let sourceTotal = 0;
let webpTotal = 0;

for (const name of names) {
  const sourcePath = path.join(pilotDir, name);
  const webpName = name.replace(/\.png$/i, ".webp");
  const webpPath = path.join(pilotDir, webpName);
  const archivePath = path.join(archiveDir, name);

  const [sourceStat, sourceMeta] = await Promise.all([
    fs.stat(sourcePath),
    sharp(sourcePath).metadata(),
  ]);

  await sharp(sourcePath)
    .webp({
      quality,
      effort: 6,
      smartSubsample: true,
    })
    .toFile(webpPath);

  const [webpStat, webpMeta] = await Promise.all([
    fs.stat(webpPath),
    sharp(webpPath).metadata(),
  ]);

  if (
    sourceMeta.width !== webpMeta.width ||
    sourceMeta.height !== webpMeta.height
  ) {
    throw new Error(`Dimension drift for ${name}`);
  }
  if (webpStat.size >= sourceStat.size) {
    throw new Error(`WebP did not reduce ${name}`);
  }

  await fs.rename(sourcePath, archivePath);

  const oldUrl = `/products/pilot/${name}`;
  const newUrl = `/products/pilot/${webpName}`;
  replacements.set(oldUrl, newUrl);

  sourceTotal += sourceStat.size;
  webpTotal += webpStat.size;
  rows.push({
    name,
    webpName,
    sourceBytes: sourceStat.size,
    webpBytes: webpStat.size,
  });
}

const trackedFiles = execFileSync("git", ["ls-files"], {
  cwd: repoRoot,
  encoding: "utf8",
})
  .split("\n")
  .map((value) => value.trim())
  .filter(Boolean);

const textExtensions = new Set([
  ".json",
  ".md",
  ".py",
  ".ts",
  ".tsx",
  ".js",
  ".mjs",
  ".yml",
  ".yaml",
  ".txt",
]);

let updatedTextFiles = 0;
for (const relative of trackedFiles) {
  const extension = path.extname(relative).toLowerCase();
  if (!textExtensions.has(extension)) continue;

  const absolute = path.join(repoRoot, relative);
  let source;
  try {
    source = await fs.readFile(absolute, "utf8");
  } catch {
    continue;
  }

  let next = source;
  for (const [oldUrl, newUrl] of replacements) {
    next = next.replaceAll(oldUrl, newUrl);
  }

  if (next !== source) {
    await fs.writeFile(absolute, next, "utf8");
    updatedTextFiles += 1;
  }
}

const saved = sourceTotal - webpTotal;
const savedPercent = (saved / sourceTotal) * 100;
const report = [
  "# DUFYND editorial WebP migration · 25 September 2026",
  "",
  `- Migrated: **${rows.length}** active storefront editorial assets`,
  `- Source PNG total: **${(sourceTotal / 1_000_000).toFixed(2)} MB**`,
  `- Public WebP total: **${(webpTotal / 1_000_000).toFixed(2)} MB**`,
  `- Public media reduction: **${(saved / 1_000_000).toFixed(2)} MB (${savedPercent.toFixed(2)}%)**`,
  `- Encoding: **WebP q=${quality}, effort=6, smart subsampling**`,
  `- Updated tracked text files: **${updatedTextFiles}**`,
  "",
  "The original PNG masters were moved out of the storefront public directory to",
  "`examples/retail/review-assets/editorial-source-png/`. They remain available",
  "for future re-encoding or visual comparison but are not shipped as public assets.",
  "",
  "| Asset | PNG bytes | WebP bytes | Saving |",
  "| --- | ---: | ---: | ---: |",
  ...rows.map((row) => {
    const percent =
      ((row.sourceBytes - row.webpBytes) / row.sourceBytes) * 100;
    return `| ${row.webpName} | ${row.sourceBytes} | ${row.webpBytes} | ${percent.toFixed(2)}% |`;
  }),
  "",
].join("\n");

await fs.writeFile(reportPath, report, "utf8");

console.log(
  `Migrated ${rows.length} DUFYND editorials: ` +
    `${(sourceTotal / 1_000_000).toFixed(1)} MB -> ` +
    `${(webpTotal / 1_000_000).toFixed(1)} MB; ` +
    `${updatedTextFiles} tracked text files updated.`,
);
