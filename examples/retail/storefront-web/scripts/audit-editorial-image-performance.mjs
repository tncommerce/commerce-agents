import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import sharp from "sharp";

const here = path.dirname(fileURLToPath(import.meta.url));
const storefrontRoot = path.resolve(here, "..");

const args = process.argv.slice(2);
const valueFor = (flag, fallback) => {
  const index = args.indexOf(flag);
  return index >= 0 && args[index + 1] ? args[index + 1] : fallback;
};

const inputDir = path.resolve(
  storefrontRoot,
  valueFor("--input", "public/products/pilot"),
);
const outputDir = path.resolve(
  storefrontRoot,
  valueFor("--out", ".image-opt-audit"),
);
const quality = Math.min(
  100,
  Math.max(1, Number(valueFor("--quality", "86")) || 86),
);

await fs.rm(outputDir, { recursive: true, force: true });
await fs.mkdir(path.join(outputDir, "images"), { recursive: true });

const entries = (await fs.readdir(inputDir))
  .filter((name) => name.toLowerCase().endsWith(".png"))
  .sort((a, b) => a.localeCompare(b));

const report = {
  generated_at: new Date().toISOString(),
  quality,
  input_dir: path.relative(storefrontRoot, inputDir),
  files: [],
  summary: {
    file_count: 0,
    source_bytes: 0,
    webp_bytes: 0,
    saved_bytes: 0,
    saved_percent: 0,
  },
};

for (const name of entries) {
  const sourcePath = path.join(inputDir, name);
  const webpName = name.replace(/\.png$/i, ".webp");
  const outputPath = path.join(outputDir, "images", webpName);

  const [sourceStat, metadata] = await Promise.all([
    fs.stat(sourcePath),
    sharp(sourcePath).metadata(),
  ]);

  await sharp(sourcePath)
    .webp({
      quality,
      effort: 6,
      smartSubsample: true,
    })
    .toFile(outputPath);

  const outputStat = await fs.stat(outputPath);
  const savedBytes = sourceStat.size - outputStat.size;
  const savedPercent =
    sourceStat.size > 0 ? (savedBytes / sourceStat.size) * 100 : 0;

  report.files.push({
    source: name,
    output: webpName,
    width: metadata.width ?? null,
    height: metadata.height ?? null,
    source_bytes: sourceStat.size,
    webp_bytes: outputStat.size,
    saved_bytes: savedBytes,
    saved_percent: Number(savedPercent.toFixed(2)),
  });

  report.summary.source_bytes += sourceStat.size;
  report.summary.webp_bytes += outputStat.size;
}

report.summary.file_count = report.files.length;
report.summary.saved_bytes =
  report.summary.source_bytes - report.summary.webp_bytes;
report.summary.saved_percent = Number(
  (
    (report.summary.saved_bytes / Math.max(1, report.summary.source_bytes)) *
    100
  ).toFixed(2),
);

await fs.writeFile(
  path.join(outputDir, "report.json"),
  JSON.stringify(report, null, 2) + "\n",
  "utf8",
);

console.log(
  `DUFYND editorial image audit: ${report.summary.file_count} files, ` +
    `${(report.summary.source_bytes / 1_000_000).toFixed(1)} MB -> ` +
    `${(report.summary.webp_bytes / 1_000_000).toFixed(1)} MB ` +
    `(${report.summary.saved_percent}% saved) at WebP q=${quality}`,
);
