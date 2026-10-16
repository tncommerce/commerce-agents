import { mkdir } from "node:fs/promises";
import path from "node:path";
import sharp from "sharp";

const clampByte = value => Math.max(0, Math.min(255, Math.round(value)));

/**
 * QA-only stills from the exact opt-in WebGL object.
 * Two identical frames over black/white backdrops reconstruct transparency
 * without cutting out beige backgrounds, labels or glass edges by hand.
 * Candidates are INTERNAL artifacts, never auto-published as storefront assets.
 */
export async function capturePerfumeStudioPoster(page, outputDir, state) {
  if (!["closed", "open"].includes(state)) throw new Error("Unknown bottle still state");
  const canvas = page.locator("[data-dufynd-spatial-canvas] canvas");
  if (await canvas.count() !== 1) throw new Error("Poster capture requires one live Three.js canvas");
  const captures = [];
  const captureCss = [
    "html {background:var(--studio-capture-bg)!important}",
    "body,body * {background-color:transparent!important;background-image:none!important;box-shadow:none!important}",
    "body *::before,body *::after {visibility:hidden!important}",
    "[data-dufynd-bottle] [data-dufynd-spatial-poster],",
    "[data-dufynd-bottle] [aria-hidden],",
    "[data-dufynd-bottle] figcaption {visibility:hidden!important}",
    "[data-dufynd-spatial-canvas],[data-dufynd-spatial-canvas] canvas {visibility:visible!important}"
  ].join("\n");
  const style = await page.addStyleTag({ content: captureCss });
  try {
    for (const background of ["#000000", "#ffffff"]) {
      await page.evaluate(color => {
        document.documentElement.style.setProperty("--studio-capture-bg", color);
      }, background);
      const bytes = await canvas.screenshot({ type: "png", animations: "disabled" });
      const { data, info } = await sharp(bytes).removeAlpha().raw().toBuffer({ resolveWithObject: true });
      captures.push({ data, width: info.width, height: info.height });
    }
  } finally {
    await style.evaluate(element => element.remove());
    await page.evaluate(() => document.documentElement.style.removeProperty("--studio-capture-bg"));
  }
  const [black, white] = captures;
  if (black.width !== white.width || black.height !== white.height) {
    throw new Error("Transparent scene capture dimensions changed");
  }
  const pixelCount = black.width * black.height;
  const rgba = Buffer.alloc(pixelCount * 4);
  let occupied = 0;
  for (let index = 0; index < pixelCount; index++) {
    const j = index * 3, k = index * 4;
    const delta = (white.data[j] - black.data[j] + white.data[j + 1] - black.data[j + 1]
      + white.data[j + 2] - black.data[j + 2]) / 3;
    const alpha = Math.max(0, Math.min(1, 1 - delta / 255));
    if (alpha < .045) continue;
    occupied++;
    rgba[k] = clampByte(black.data[j] / alpha);
    rgba[k + 1] = clampByte(black.data[j + 1] / alpha);
    rgba[k + 2] = clampByte(black.data[j + 2] / alpha);
    rgba[k + 3] = clampByte(alpha * 255);
  }
  if (occupied < pixelCount * .01) throw new Error("Original glass scene captured empty");
  const targetDir = path.join(outputDir, "poster-candidates");
  await mkdir(targetDir, { recursive: true });
  const target = path.join(targetDir, "perfume-study-" + state + ".webp");
  await sharp(rgba, { raw: { width: black.width, height: black.height, channels: 4 } })
    .resize(700, 660, { fit: "contain", background: { r: 0, g: 0, b: 0, alpha: 0 } })
    .webp({ quality: 94, alphaQuality: 100, effort: 5 })
    .toFile(target);
  return { target, source_width: black.width, source_height: black.height, occupied_pixels: occupied };
}
