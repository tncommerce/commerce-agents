import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";

import { chromium } from "playwright";

const args = process.argv.slice(2);
const valueFor = (flag, fallback) => {
  const index = args.indexOf(flag);
  return index >= 0 && args[index + 1] ? args[index + 1] : fallback;
};

const baseUrl = valueFor("--base-url", "http://127.0.0.1:3000").replace(/\/$/, "");
const outputDir = path.resolve(valueFor("--out", ".visual-qa"));

const viewports = [
  { name: "320", width: 320, height: 780 },
  { name: "390", width: 390, height: 844 },
  { name: "768", width: 768, height: 1024 },
  { name: "1440", width: 1440, height: 1000 },
];

const routes = [
  { name: "home", route: "/", marker: "Finde den Duft, der wirklich zu dir passt." },
  { name: "catalog", route: "/duft", marker: "Parfums entdecken" },
  { name: "naxos", route: "/duft/xerjoff-naxos", marker: "Naxos" },
  { name: "absolu-aventus", route: "/duft/creed-absolu-aventus", marker: "Absolu Aventus" },
  { name: "prada-lhomme", route: "/duft/prada-lhomme", marker: "L'Homme" },
  { name: "bois-imperial", route: "/duft/essential-parfums-bois-imperial", marker: "Bois Impérial" },
  {
    name: "swy-intensely",
    route: "/duft/giorgio-armani-stronger-with-you-intensely",
    marker: "Stronger With You Intensely",
  },
  { name: "vibrato", route: "/duft/sospiro-vibrato", marker: "Vibrato" },
];

const forbiddenUi = [
  "Out of stock",
  "Launch Spotlight",
  "3D View",
  "Immersive View",
  "Performance",
];

const naxosGermanNotes = [
  "Lavendel",
  "Bergamotte",
  "Omanischer Weihrauch",
  "Zitrone",
  "Honig",
  "Sambac-Jasmin",
  "Kaschmir",
  "Zimt",
  "Tabak",
  "Tonkabohne",
  "Vanille",
];

await mkdir(outputDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const report = {
  generated_at: new Date().toISOString(),
  base_url: baseUrl,
  checks: [],
  failures: [],
};

try {
  for (const viewport of viewports) {
    const context = await browser.newContext({
      viewport: { width: viewport.width, height: viewport.height },
      deviceScaleFactor: 1,
      reducedMotion: "reduce",
    });
    const page = await context.newPage();

    for (const target of routes) {
      const label = `${target.name}-${viewport.name}`;
      const url = `${baseUrl}${target.route}`;

      try {
        const response = await page.goto(url, {
          waitUntil: "domcontentloaded",
          timeout: 45_000,
        });
        if (!response || !response.ok()) {
          throw new Error(`HTTP ${response?.status() ?? "no response"}`);
        }

        await page.getByText(target.marker, { exact: false }).first().waitFor({
          state: "visible",
          timeout: 20_000,
        });
        await page.waitForTimeout(500);

        await page.evaluate(async () => {
          const step = Math.max(320, Math.floor(window.innerHeight * 0.75));
          for (let y = 0; y < document.documentElement.scrollHeight; y += step) {
            window.scrollTo(0, y);
            await new Promise((resolve) => setTimeout(resolve, 35));
          }
          window.scrollTo(0, 0);
        });
        await page.waitForTimeout(350);

        const diagnostics = await page.evaluate((blocked) => {
          const bodyText = document.body.innerText;
          const visibleBrokenImages = Array.from(document.images)
            .filter((image) => {
              const rect = image.getBoundingClientRect();
              const style = window.getComputedStyle(image);
              return (
                style.display !== "none" &&
                style.visibility !== "hidden" &&
                rect.width > 1 &&
                rect.height > 1 &&
                image.complete &&
                image.naturalWidth === 0
              );
            })
            .map((image) => image.getAttribute("src") || "(missing src)");

          return {
            title: document.title,
            body_length: bodyText.length,
            horizontal_overflow:
              document.documentElement.scrollWidth - window.innerWidth,
            visible_broken_images: visibleBrokenImages,
            forbidden_ui: blocked.filter((phrase) => bodyText.includes(phrase)),
            directory_listing:
              bodyText.includes("Index of /") ||
              bodyText.includes("Directory listing for"),
          };
        }, forbiddenUi);

        if (diagnostics.body_length < 250) {
          throw new Error(`page content unexpectedly short: ${diagnostics.body_length}`);
        }
        if (diagnostics.horizontal_overflow > 2) {
          throw new Error(
            `horizontal overflow: ${diagnostics.horizontal_overflow}px`,
          );
        }
        if (diagnostics.visible_broken_images.length) {
          throw new Error(
            `broken images: ${diagnostics.visible_broken_images.join(", ")}`,
          );
        }
        if (diagnostics.forbidden_ui.length) {
          throw new Error(
            `English UI regression: ${diagnostics.forbidden_ui.join(", ")}`,
          );
        }
        if (diagnostics.directory_listing) {
          throw new Error("directory listing detected instead of storefront content");
        }

        if (target.name === "naxos") {
          if (viewport.width < 1024) {
            const notesDetails = page
              .locator("details")
              .filter({ hasText: "Duftnoten" })
              .first();
            if (await notesDetails.isVisible()) {
              const isOpen = await notesDetails.evaluate(
                (element) => element.hasAttribute("open"),
              );
              if (!isOpen) {
                await notesDetails.locator("summary").click();
              }
            }
          }

          const verifiedCutout = page.locator(
            'img[src="/products/naxos-cutout-production.png"]',
          );
          if ((await verifiedCutout.count()) < 1) {
            throw new Error("Naxos verified cutout is missing");
          }

          const text = await page.locator("body").innerText();
          const missingNotes = naxosGermanNotes.filter(
            (note) => !text.includes(note),
          );
          if (missingNotes.length) {
            throw new Error(
              `Naxos German note labels missing: ${missingNotes.join(", ")}`,
            );
          }

          const notesMissingIcons = await page.evaluate((expectedNotes) => {
            const spans = Array.from(document.querySelectorAll("span"));
            return expectedNotes.filter(
              (note) =>
                !spans.some(
                  (span) =>
                    span.textContent?.trim() === note &&
                    Boolean(span.querySelector("svg")),
                ),
            );
          }, naxosGermanNotes);
          if (notesMissingIcons.length) {
            throw new Error(
              `Naxos note icons missing in rendered layout: ${notesMissingIcons.join(", ")}`,
            );
          }

          if ((await page.locator("model-viewer").count()) > 0) {
            throw new Error(
              "Naxos exposed a true 3D viewer without a verified model_3d asset",
            );
          }

          const disclosure = text.includes(
            "Bild: stilisierte DUFYND-Inszenierung",
          );
          if (disclosure) {
            throw new Error(
              "Naxos verified truth hero is incorrectly disclosed as editorial",
            );
          }

          const expectedGalleryText = [
            "Weitere Ansichten",
            "Freisteller",
            "DUFYND Inszenierung",
            "Verifiziert",
            "Editorial",
          ];
          const normalizedGalleryText = text.toLocaleLowerCase("de-DE");
          const missingGalleryText = expectedGalleryText.filter(
            (label) =>
              !normalizedGalleryText.includes(
                label.toLocaleLowerCase("de-DE"),
              ),
          );
          if (missingGalleryText.length) {
            throw new Error(
              `Naxos multi-visual gallery is incomplete: ${missingGalleryText.join(", ")}`,
            );
          }

          const editorialAsset = page.locator(
            'img[src="/products/pilot/xerjoff-naxos-editorial.png"]',
          );
          if ((await editorialAsset.count()) < 1) {
            throw new Error("Naxos editorial gallery asset is missing");
          }
        }

        if (
          [
            "absolu-aventus",
            "prada-lhomme",
            "bois-imperial",
            "swy-intensely",
            "vibrato",
          ].includes(target.name)
        ) {
          const text = await page.locator("body").innerText();
          if (!text.includes("Bild: stilisierte DUFYND-Inszenierung")) {
            throw new Error(
              "unverified P0 visual is missing editorial disclosure",
            );
          }
        }

        if (target.name === "catalog") {
          const naxosCardTruth = page.locator(
            'a[href="/duft/xerjoff-naxos"] img[src="/products/naxos-cutout-production.png"]',
          );
          if ((await naxosCardTruth.count()) < 1) {
            throw new Error(
              "catalog does not prioritize the Naxos verified cutout",
            );
          }
        }

        if (target.name === "home") {
          const spotlightTruth = page.locator(
            'a[href="/duft/xerjoff-naxos"] img[src="/products/naxos-cutout-production.png"]',
          );
          if ((await spotlightTruth.count()) < 1) {
            throw new Error(
              "homepage spotlight does not prioritize the Naxos verified cutout",
            );
          }
        }

        await page.screenshot({
          path: path.join(outputDir, `${label}.png`),
          fullPage: true,
        });

        report.checks.push({
          label,
          status: "passed",
          ...diagnostics,
        });
      } catch (error) {
        const message =
          error instanceof Error ? error.message : String(error);
        report.failures.push({ label, url, message });
        report.checks.push({ label, status: "failed", message });

        try {
          await page.screenshot({
            path: path.join(outputDir, `${label}-FAILED.png`),
            fullPage: true,
          });
        } catch {
          // Keep the original QA failure.
        }
      }
    }

    await context.close();
  }
} finally {
  await browser.close();
}

await writeFile(
  path.join(outputDir, "report.json"),
  JSON.stringify(report, null, 2) + "\n",
  "utf8",
);

if (report.failures.length) {
  console.error(JSON.stringify(report.failures, null, 2));
  process.exit(1);
}

console.log(
  `DUFYND visual QA passed: ${report.checks.length} responsive page checks.`,
);
