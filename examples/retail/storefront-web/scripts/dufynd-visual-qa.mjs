import { mkdir, readFile, writeFile } from "node:fs/promises";
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
const imageDecodeTimeoutMs = 8_000;

const sourceCatalog = JSON.parse(
  await readFile(
    new URL("../../data/scentai_products.json", import.meta.url),
    "utf-8",
  ),
);
function hasValidationBlockers(product) {
  const blockers = Array.isArray(product?.validation?.blockers)
    ? product.validation.blockers
    : [];

  return blockers.some((blocker) => String(blocker || "").trim());
}

function slugifyFragrance(value) {
  return String(value || "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[’']/g, "")
    .replace(/&/g, " und ")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

const expectedFragranceCount = sourceCatalog.products.filter(
  (product) =>
    String(product?.product_id || "").startsWith("SC-") &&
    !hasValidationBlockers(product),
).length;

const blockedFragranceRoutes = new Set(
  sourceCatalog.products
    .filter(
      (product) =>
        String(product?.product_id || "").startsWith("SC-") &&
        hasValidationBlockers(product),
    )
    .map(
      (product) =>
        `/duft/${slugifyFragrance(
          `${String(product?.brand || "").trim()} ${String(product?.name || "").trim()}`,
        )}`,
    ),
);

const viewports = [
  { name: "320", width: 320, height: 780 },
  { name: "390", width: 390, height: 844 },
  { name: "768", width: 768, height: 1024 },
  { name: "1440", width: 1440, height: 1000 },
];

const coreRoutes = [
  { name: "home", route: "/", marker: "Finde den Duft, der wirklich zu dir passt." },
  {
    name: "social-start",
    route: "/start",
    marker: "Finde deinen schnellsten Weg zum passenden Duft.",
  },
  {
    name: "acquisition-duftfinder",
    route: "/duftfinder",
    marker: "Finde einen Duft, der zu dir und deinem Alltag passt.",
  },
  { name: "catalog", route: "/duft", marker: "Parfums entdecken" },
  {
    name: "comparisons",
    route: "/vergleich?left=SC-XERJOFF-NAXOS-100&right=SC-SOSPIRO-VIBRATO-100",
    marker: "Duft-DNA auf einen Blick",
  },
  {
    name: "comparison-turathi-tygar",
    route: "/vergleich/afnan-perfumes-turathi-blue-vs-bvlgari-le-gemme-tygar",
    marker: "DUFYND · Duftvergleich",
  },
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
  { name: "widian-london", route: "/duft/widian-london", marker: "London" },
];

const routes = coreRoutes.filter(
  ({ route }) => !blockedFragranceRoutes.has(route),
);

const forbiddenUi = [
  "Out of stock",
  "Launch Spotlight",
  "3D View",
  "Immersive View",
  "Performance",
  "Verified Product Truth",
  "Exploded View",
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

const naxosPremiumMotifs = {
  Lavendel: "lavender",
  Bergamotte: "bergamot",
  "Omanischer Weihrauch": "incense",
  Zitrone: "lemon",
  Honig: "honey",
  "Sambac-Jasmin": "jasmine",
  Zimt: "spice",
  Tabak: "tobacco",
  Tonkabohne: "tonka",
  Vanille: "vanilla",
};

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

        // Full-page screenshots can capture below-the-fold lazy images before they
        // finish loading. Decode each rendered image so the visual artifact is
        // suitable for review rather than a page of temporary empty stages.
        const unsettledImages = await page.evaluate(
          async (decodeTimeoutMs) => {
            const images = Array.from(document.images).filter((image) => {
              const style = window.getComputedStyle(image);
              return (
                image.getAttribute("src") &&
                style.display !== "none" &&
                style.visibility !== "hidden"
              );
            });

            await Promise.all(
              images.map(async (image) => {
                image.loading = "eager";
                await Promise.race([
                  image.decode().catch(() => undefined),
                  new Promise((resolve) =>
                    window.setTimeout(resolve, decodeTimeoutMs),
                  ),
                ]);
              }),
            );

            return images
              .filter((image) => !image.complete)
              .map((image) => image.getAttribute("src") || "(missing src)");
          },
          imageDecodeTimeoutMs,
        );

        if (unsettledImages.length) {
          throw new Error(
            `images did not settle within ${imageDecodeTimeoutMs}ms: ${unsettledImages.join(", ")}`,
          );
        }

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

        if (target.route.startsWith("/duft/")) {
          const layout = await page.evaluate(() => {
            const rect = (selector) =>
              document.querySelector(selector)?.getBoundingClientRect() || null;
            const title = rect(".dufynd-fragrance-hero h1");
            const stage = rect(".dufynd-fragrance-hero .dufynd-product-stage, .dufynd-fragrance-hero .dufynd-editorial-depth-stage, .dufynd-fragrance-hero .dufynd-model-stage");
            const cutout = rect(".dufynd-fragrance-hero .dufynd-product-image");
            const offers = rect("#angebote");
            const exploded = rect(".dufynd-exploded-notes");
            return {
              title_top: title ? title.top + window.scrollY : null,
              stage_top: stage ? stage.top + window.scrollY : null,
              stage_height: stage?.height ?? null,
              cutout_clipped: Boolean(stage && cutout && (
                cutout.top < stage.top - 2 || cutout.bottom > stage.bottom + 2 ||
                cutout.left < stage.left - 2 || cutout.right > stage.right + 2
              )),
              offers_after_exploded: Boolean(offers && exploded && offers.top > exploded.top),
            };
          });
          const mobileProductFirst = viewport.width <= 390;
          const maxIdentityTop = mobileProductFirst ? 620 : 260;
          if (layout.title_top == null || layout.title_top > maxIdentityTop) {
            throw new Error(`fragrance identity starts too far below the intended first-screen composition: ${layout.title_top}px`);
          }
          if (
            mobileProductFirst &&
            (
              layout.stage_top == null ||
              layout.title_top == null ||
              layout.stage_top >= layout.title_top
            )
          ) {
            throw new Error(
              "mobile fragrance detail no longer presents the product stage before identity copy",
            );
          }
          if (
            mobileProductFirst &&
            (layout.stage_height == null || layout.stage_height > 270)
          ) {
            throw new Error(`mobile fragrance visual is too tall: ${layout.stage_height}px`);
          }
          if (layout.cutout_clipped) {
            throw new Error("verified bottle cutout extends beyond its hero stage");
          }
          const journey = await page.locator(".dufynd-fragrance-journey").count();
          if (journey !== 1) {
            throw new Error(`fragrance detail is missing its scroll journey: ${journey}`);
          }
          const journeyOrder = await page.evaluate(() => {
            const rectTop = (selector) =>
              document.querySelector(selector)?.getBoundingClientRect().top ?? null;
            return {
              offers: rectTop("#angebote"),
              profile: rectTop("#duftprofil"),
            };
          });
          if (
            journeyOrder.offers == null ||
            journeyOrder.profile == null ||
            journeyOrder.offers >= journeyOrder.profile
          ) {
            throw new Error("fragrance journey chapter order is invalid");
          }
          if (layout.offers_after_exploded) {
            throw new Error("merchant offers appear after the exploded-note view");
          }
        }

        if (target.route.startsWith("/duft/")) {
          const productSchema = await page.evaluate(() => {
            const schemas = Array.from(
              document.querySelectorAll('script[type="application/ld+json"]'),
            )
              .map((script) => {
                try {
                  return JSON.parse(script.textContent || "{}");
                } catch {
                  return null;
                }
              })
              .filter(Boolean);

            return schemas.find((schema) => schema?.["@type"] === "Product") || null;
          });

          if (!productSchema) {
            throw new Error("fragrance detail page is missing Product JSON-LD");
          }

          if (!String(productSchema.name || "").trim()) {
            throw new Error("Product JSON-LD has no usable product name");
          }

          const schemaImages = Array.isArray(productSchema.image)
            ? productSchema.image
            : productSchema.image
              ? [productSchema.image]
              : [];

          if (target.name === "naxos") {
            if (
              !schemaImages.some((image) =>
                String(image).endsWith("/products/naxos-cutout-production.webp"),
              )
            ) {
              throw new Error(
                "Naxos Product JSON-LD does not use the verified cutout",
              );
            }
          } else if (schemaImages.length > 0) {
            throw new Error(
              "unverified fragrance exposed an image as Product JSON-LD truth",
            );
          }
        }

        if (
          viewport.width < 640 &&
          target.route.startsWith("/duft/")
        ) {
          const mobileOfferBar = page.locator(".dufynd-mobile-offer-bar");
          const heroOfferCta = page.locator("#dufynd-hero-offer-cta");
          const heroCtaVisible = await heroOfferCta.evaluate((element) => {
            const bounds = element.getBoundingClientRect();
            return (
              bounds.bottom > 0 &&
              bounds.top < window.innerHeight &&
              bounds.right > 0 &&
              bounds.left < window.innerWidth
            );
          });
          if (heroCtaVisible && (await mobileOfferBar.count()) !== 0) {
            throw new Error(
              "mobile offer bar duplicates the visible hero CTA",
            );
          }

          await page.locator("#angebote").evaluate((element) => {
            const bounds = element.getBoundingClientRect();
            const targetTop =
              window.scrollY +
              bounds.top +
              Math.min(80, window.innerHeight * 0.1);
            window.scrollTo({ top: targetTop, behavior: "instant" });
          });
          await page.waitForFunction(
            () => {
              const offers = document.querySelector("#angebote");
              if (!offers) return false;
              const bounds = offers.getBoundingClientRect();
              return (
                bounds.bottom > 0 &&
                bounds.top < window.innerHeight &&
                !document.querySelector(".dufynd-mobile-offer-bar")
              );
            },
            undefined,
            { timeout: 2000 },
          );

          await page.locator("#angebote").evaluate((element) => {
            const bounds = element.getBoundingClientRect();
            const targetTop =
              window.scrollY +
              bounds.bottom +
              Math.max(48, window.innerHeight * 0.08);
            window.scrollTo({ top: targetTop, behavior: "instant" });
          });
          await page.waitForFunction(
            () => {
              const trigger = document.querySelector("#dufynd-hero-offer-cta");
              const offers = document.querySelector("#angebote");
              const bar = document.querySelector(".dufynd-mobile-offer-bar");
              if (!trigger || !offers || !bar) return false;
              const triggerBounds = trigger.getBoundingClientRect();
              const offerBounds = offers.getBoundingClientRect();
              return (
                triggerBounds.bottom <= 0 &&
                offerBounds.bottom <= 0 &&
                bar.getBoundingClientRect().height > 0
              );
            },
            undefined,
            { timeout: 2000 },
          );

          if (
            (await mobileOfferBar.count()) !== 1 ||
            !(await mobileOfferBar.isVisible())
          ) {
            throw new Error(
              "mobile fragrance page does not reveal the fixed offer bar after both offer entry points leave view",
            );
          }

          const bottomPadding = await mobileOfferBar.evaluate((element) => {
            const value = Number.parseFloat(
              window.getComputedStyle(element).paddingBottom,
            );
            return Number.isFinite(value) ? value : 0;
          });
          if (bottomPadding < 9.5) {
            throw new Error(
              `mobile offer bar lacks safe-area bottom padding: ${bottomPadding}px`,
            );
          }

          await page.evaluate(() => window.scrollTo(0, 0));
          await page.waitForTimeout(120);
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
            'img[src="/products/naxos-cutout-production.webp"]',
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
            const noteChips = Array.from(
              document.querySelectorAll("span, a"),
            );
            return expectedNotes.filter(
              (note) =>
                !noteChips.some(
                  (chip) =>
                    chip.textContent?.replace("→", "").trim() === note &&
                    Boolean(chip.querySelector("svg")),
                ),
            );
          }, naxosGermanNotes);
          if (notesMissingIcons.length) {
            throw new Error(
              `Naxos note icons missing in rendered layout: ${notesMissingIcons.join(", ")}`,
            );
          }

          const missingPremiumMotifs = await page.evaluate(
            (expectedMotifs) =>
              Object.values(expectedMotifs).filter(
                (motif) =>
                  !document.querySelector(
                    `svg[data-dufynd-note-motif="${motif}"]`,
                  ),
              ),
            naxosPremiumMotifs,
          );
          if (missingPremiumMotifs.length) {
            throw new Error(
              `Naxos premium note motifs missing: ${missingPremiumMotifs.join(", ")}`,
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
            "Redaktionell",
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

          const backdropAsset = page.locator(
            'img[src="/products/naxos-bottle-free-backdrop.webp"]',
          );
          if ((await backdropAsset.count()) < 1) {
            throw new Error("Naxos bottle-free editorial backdrop is missing");
          }

          const legacyEditorial = page.locator(
            'img[src="/products/pilot/xerjoff-naxos-editorial.png"]',
          );
          if ((await legacyEditorial.count()) > 0) {
            throw new Error(
              "Naxos legacy bottle-containing editorial is still rendered",
            );
          }

          const explodedSection = page.locator(
            '[aria-labelledby="dufynd-exploded-heading"]',
          );
          if ((await explodedSection.count()) !== 1) {
            throw new Error(
              "Naxos verified product is missing the exploded-notes view",
            );
          }

          const explodedStageCollapsed = explodedSection.locator(
            '#dufynd-exploded-stage[data-expanded="false"][aria-hidden="true"]',
          );
          if ((await explodedStageCollapsed.count()) !== 1) {
            throw new Error(
              "Naxos collapsed exploded-notes stage is not hidden from assistive technology",
            );
          }
          if (viewport.width <= 480) {
            const collapsedHeight = await explodedStageCollapsed.evaluate(
              (element) => element.getBoundingClientRect().height,
            );
            if (collapsedHeight > 330) {
              throw new Error(
                `Naxos collapsed exploded-notes stage is too tall on mobile: ${collapsedHeight}px`,
              );
            }
          }

          const explodedButton = explodedSection.locator(
            'button[aria-controls="dufynd-exploded-stage"]',
          );
          if ((await explodedButton.innerText()).trim() !== "Duftaufbau entfalten") {
            throw new Error("Naxos exploded-notes toggle has an unexpected collapsed label");
          }
          if ((await explodedButton.getAttribute("aria-expanded")) !== "false") {
            throw new Error(
              "Naxos exploded-notes toggle does not expose collapsed state",
            );
          }
          await explodedButton.click();
          if ((await explodedButton.getAttribute("aria-expanded")) !== "true") {
            throw new Error(
              "Naxos exploded-notes toggle does not expose expanded state",
            );
          }

          const explodedStage = explodedSection.locator(
            '#dufynd-exploded-stage[data-expanded="true"]:not([aria-hidden="true"])',
          );
          if ((await explodedStage.count()) !== 1) {
            throw new Error(
              "Naxos exploded-notes interaction did not enter expanded state",
            );
          }
          if (viewport.width <= 480) {
            // The mobile min-height expands over 420 ms. Wait for the rendered
            // state rather than sampling two frames into the transition.
            await page.waitForFunction(
              () =>
                (document.querySelector("#dufynd-exploded-stage")?.getBoundingClientRect()
                  .height ?? 0) >= 430,
              null,
              { timeout: 2000 },
            );
            const expandedHeight = await explodedStage.evaluate(
              (element) => element.getBoundingClientRect().height,
            );
            if (expandedHeight < 430) {
              throw new Error(
                `Naxos expanded exploded-notes stage is too short on mobile: ${expandedHeight}px`,
              );
            }
          }

          const explodedNotes = explodedSection.locator(
            "[data-dufynd-exploded-note]",
          );
          if ((await explodedNotes.count()) < 6) {
            throw new Error(
              "Naxos exploded-notes view has insufficient note layers",
            );
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

          if (
            (await page.locator(
              '[aria-labelledby="dufynd-exploded-heading"]',
            ).count()) > 0
          ) {
            throw new Error(
              "unverified product exposed the verified-only exploded-notes view",
            );
          }
        }

        if (target.name === "comparisons") {
          if ((await page.locator(".dufynd-comparison-picker").count()) !== 1) {
            throw new Error("free comparison is missing the immersive picker surface");
          }
          if ((await page.locator(".dufynd-comparison-live-stage").count()) !== 1) {
            throw new Error("free comparison is missing the immersive dual stage");
          }
          if ((await page.locator(".dufynd-comparison-product-card").count()) !== 2) {
            throw new Error(
              `free comparison expected 2 product stages, got ${await page.locator(".dufynd-comparison-product-card").count()}`,
            );
          }
        }

        if (target.name === "comparison-turathi-tygar") {
          if ((await page.locator(".dufynd-comparison-dual-stage").count()) !== 1) {
            throw new Error("documented comparison is missing the immersive dual stage");
          }
          if ((await page.locator(".dufynd-comparison-product-card").count()) !== 2) {
            throw new Error(
              `documented comparison expected 2 product stages, got ${await page.locator(".dufynd-comparison-product-card").count()}`,
            );
          }
        }

        if (target.name === "catalog") {
          const catalogPage = page.locator("main.dufynd-catalog-page");
          if ((await catalogPage.count()) !== 1) {
            throw new Error(
              "catalog is missing the DUFYND editorial page ground",
            );
          }
          const discoveryHero = page.locator(
            ".dufynd-catalog-discovery-hero",
          );
          if ((await discoveryHero.count()) !== 1) {
            throw new Error(
              "catalog is missing the immersive discovery hero",
            );
          }
          const discoveryBottles = page.locator(
            ".dufynd-catalog-discovery-bottle",
          );
          if ((await discoveryBottles.count()) !== 3) {
            throw new Error(
              `catalog discovery hero expected 3 fragrance spotlights, got ${await discoveryBottles.count()}`,
            );
          }
          if (
            (await page.locator('a[href="#dufynd-katalog"]').count()) !== 1
          ) {
            throw new Error(
              "catalog discovery hero is missing its catalog jump CTA",
            );
          }
          if ((await page.locator("header.dufynd-catalog-header").count()) !== 1) {
            throw new Error(
              "catalog is missing the scoped DUFYND header treatment",
            );
          }

          const catalogCards = page.locator('article');
          const catalogLoadMore = page.getByRole("button", {
            name: /Weitere 12 Düfte anzeigen/,
          });
          if ((await catalogCards.count()) !== 12) {
            throw new Error(
              `catalog initial browse should render 12 cards, got ${await catalogCards.count()}`,
            );
          }
          const immersiveCatalogCards = page.locator(
            "article.dufynd-catalog-card",
          );
          const immersiveCardStages = page.locator(
            "[data-dufynd-catalog-card-stage]",
          );
          if ((await immersiveCatalogCards.count()) !== 12) {
            throw new Error(
              `catalog immersive card count mismatch: ${await immersiveCatalogCards.count()}`,
            );
          }
          if ((await immersiveCardStages.count()) !== 12) {
            throw new Error(
              `catalog immersive visual-stage count mismatch: ${await immersiveCardStages.count()}`,
            );
          }
          if ((await catalogLoadMore.count()) !== 1) {
            throw new Error(
              "catalog initial browse is missing progressive disclosure",
            );
          }
          const catalogSummary = await page.locator("body").innerText();
          if (!catalogSummary.includes("12 angezeigt")) {
            throw new Error(
              "catalog does not disclose the initial visible result count",
            );
          }

          const naxosCardTruth = page.locator(
            'a[href="/duft/xerjoff-naxos"] img[src="/products/naxos-cutout-production.webp"]',
          );
          if ((await naxosCardTruth.count()) < 1) {
            throw new Error(
              "catalog does not prioritize the Naxos verified cutout",
            );
          }
        }

        if (target.name === "acquisition-duftfinder") {
          if ((await page.locator('img[src="/icon.svg"]').count()) < 1) {
            throw new Error("acquisition landing is missing the DUFYND brand mark");
          }
          if ((await page.locator(".dufynd-acquisition-stage").count()) !== 1) {
            throw new Error("acquisition landing is missing its immersive product stage");
          }
          if ((await page.locator(".dufynd-acquisition-bottle").count()) !== 3) {
            throw new Error(
              `acquisition landing expected 3 catalogue spotlights, got ${await page.locator(".dufynd-acquisition-bottle").count()}`,
            );
          }
          if ((await page.locator('a[href="/duft"]').count()) < 1) {
            throw new Error("acquisition landing is missing the catalog path");
          }
          if (
            (await page.getByText("Persönliche Beratung starten", {
              exact: true,
            }).count()) < 1
          ) {
            throw new Error("acquisition landing is missing its primary advisor CTA");
          }
        }

        if (target.name === "social-start") {
          const requiredEntryPaths = [
            "/duftfinder",
            "/duft",
            "/parfum-alternativen",
            "/parfum-geschenkberater",
          ];
          for (const href of requiredEntryPaths) {
            if ((await page.locator(`a[href="${href}"]`).count()) < 1) {
              throw new Error(`social start is missing entry path: ${href}`);
            }
          }

          if ((await page.locator('img[src="/icon.svg"]').count()) < 1) {
            throw new Error("social start is missing the DUFYND brand mark");
          }
        }

        if (target.name === "home") {
          const spotlightTruth = page.locator(
            'a[href="/duft/xerjoff-naxos"] img[src="/products/naxos-cutout-production.webp"]',
          );
          if ((await spotlightTruth.count()) < 1) {
            throw new Error(
              "homepage spotlight does not prioritize the Naxos verified cutout",
            );
          }

          if ([390, 1440].includes(viewport.width)) {
            const productControl = page
              .locator('[role="button"]:visible')
              .filter({ hasText: "Details" })
              .first();
            if ((await productControl.count()) !== 1) {
              throw new Error(
                "homepage has no visible keyboard-operable fragrance card",
              );
            }

            await productControl.focus();
            await page.keyboard.press("Space");
            await page.waitForURL(
              (current) => current.pathname.startsWith("/duft/"),
              { timeout: 5_000 },
            );
            await page.goBack({ waitUntil: "domcontentloaded" });
            await page.getByText(target.marker, { exact: false }).first().waitFor({
              state: "visible",
              timeout: 20_000,
            });
            await spotlightTruth.first().waitFor({
              state: "visible",
              timeout: 20_000,
            });
            await spotlightTruth.first().evaluate(async (image) => {
              image.loading = "eager";
              if (!image.complete || image.naturalWidth === 0) {
                await image.decode();
              }
            });
            await page.waitForTimeout(100);
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

  // The full catalog selection should survive sharing and reloads,
  // without discarding acquisition attribution from the incoming link.
  const shareContext = await browser.newContext();
  try {
    const sharePage = await shareContext.newPage();
    const shareResponse = await sharePage.goto(
      `${baseUrl}/duft?utm_source=qa&profil=freshness`,
      { waitUntil: "networkidle" },
    );
    if (!shareResponse?.ok()) {
      throw new Error("catalog share link did not load");
    }
    const freshProfile = sharePage.locator(
      'section[aria-label="Duftgefühl entdecken"] button[aria-pressed]',
    ).first();
    if ((await freshProfile.getAttribute("aria-pressed")) !== "true") {
      throw new Error("catalog did not restore the shared scent world");
    }
    await sharePage.getByRole("searchbox", { name: "Duft, Marke oder Profil" }).fill("Naxos");
    await sharePage.getByRole("button", { name: "Herren", exact: true }).click();
    await sharePage.getByRole("combobox", { name: "Marke" }).selectOption("Xerjoff");
    await sharePage.getByRole("combobox", { name: "Bewertung" }).selectOption("8");
    await sharePage.getByRole("combobox", { name: "Sortierung" }).selectOption("rating");
    await sharePage.waitForFunction(() => {
      const url = new URL(window.location.href);
      return url.searchParams.get("q") === "Naxos" &&
        url.searchParams.get("profil") === "freshness" &&
        url.searchParams.get("zielgruppe") === "men" &&
        url.searchParams.get("marke") === "Xerjoff" &&
        url.searchParams.get("bewertung") === "8" &&
        url.searchParams.get("sort") === "rating" &&
        url.searchParams.get("utm_source") === "qa";
    });
    await sharePage.reload({ waitUntil: "networkidle" });
    if ((await sharePage.getByRole("searchbox", { name: "Duft, Marke oder Profil" }).inputValue()) !== "Naxos" ||
        (await freshProfile.getAttribute("aria-pressed")) !== "true" ||
        (await sharePage.getByRole("button", { name: "Herren", exact: true }).getAttribute("aria-pressed")) !== "true" ||
        (await sharePage.getByRole("combobox", { name: "Marke" }).inputValue()) !== "Xerjoff" ||
        (await sharePage.getByRole("combobox", { name: "Bewertung" }).inputValue()) !== "8" ||
        (await sharePage.getByRole("combobox", { name: "Sortierung" }).inputValue()) !== "rating" ||
        (await sharePage.getByRole("button", { name: "Filterlink kopieren" }).count()) !== 1) {
      throw new Error("catalog did not restore the shared filters and sort order");
    }
    report.checks.push({ label: "catalog-share-link", status: "passed" });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    report.failures.push({ label: "catalog-share-link", message });
    report.checks.push({ label: "catalog-share-link", status: "failed", message });
  } finally {
    await shareContext.close();
  }

  const comparisonContext = await browser.newContext();
  try {
    const comparisonPage = await comparisonContext.newPage();
    const response = await comparisonPage.goto(
      `${baseUrl}/vergleich?utm_source=qa`,
      { waitUntil: "networkidle" },
    );
    if (!response?.ok()) throw new Error("free comparison did not load");
    await comparisonPage.getByRole("combobox", { name: "Duft 1" })
      .selectOption("SC-XERJOFF-NAXOS-100");
    await comparisonPage.getByRole("combobox", { name: "Duft 2" })
      .selectOption("SC-SOSPIRO-VIBRATO-100");
    await comparisonPage.waitForFunction(() => {
      const url = new URL(window.location.href);
      return url.searchParams.get("left") === "SC-XERJOFF-NAXOS-100" &&
        url.searchParams.get("right") === "SC-SOSPIRO-VIBRATO-100" &&
        url.searchParams.get("utm_source") === "qa";
    });
    await comparisonPage.reload({ waitUntil: "networkidle" });
    if ((await comparisonPage.getByRole("combobox", { name: "Duft 1" }).inputValue()) !== "SC-XERJOFF-NAXOS-100" ||
        (await comparisonPage.getByRole("combobox", { name: "Duft 2" }).inputValue()) !== "SC-SOSPIRO-VIBRATO-100" ||
        (await comparisonPage.getByRole("button", { name: "Vergleichslink kopieren" }).count()) !== 1) {
      throw new Error("free comparison did not restore the shared pair");
    }
    report.checks.push({ label: "comparison-share-link", status: "passed" });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    report.failures.push({ label: "comparison-share-link", message });
    report.checks.push({ label: "comparison-share-link", status: "failed", message });
  } finally {
    await comparisonContext.close();
  }

  const backupContext = await browser.newContext({ acceptDownloads: true });
  try {
    const backupPage = await backupContext.newPage();
    await backupPage.goto(`${baseUrl}/merkliste`, { waitUntil: "networkidle" });
    await backupPage.evaluate(() => {
      window.localStorage.setItem(
        "scentai_fragrance_library_v1",
        JSON.stringify({ version: 1, wishlist: ["SC-XERJOFF-NAXOS-100"], owned: [] }),
      );
    });
    await backupPage.reload({ waitUntil: "networkidle" });
    const [download] = await Promise.all([
      backupPage.waitForEvent("download"),
      backupPage.getByRole("button", { name: "Duftliste sichern" }).click(),
    ]);
    const backupPath = await download.path();
    if (!backupPath) throw new Error("library backup download is unavailable");
    await backupPage.evaluate(() => {
      window.localStorage.removeItem("scentai_fragrance_library_v1");
    });
    await backupPage.reload({ waitUntil: "networkidle" });
    await backupPage.locator('input[type="file"]').setInputFiles(backupPath);
    await backupPage.getByText("Sicherung geladen: 1 gemerkt, 0 in Sammlung.").waitFor();
    if ((await backupPage.locator('a[href="/duft/xerjoff-naxos"]').count()) !== 1) {
      throw new Error("library backup did not restore the saved fragrance");
    }
    report.checks.push({ label: "library-backup-roundtrip", status: "passed" });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    report.failures.push({ label: "library-backup-roundtrip", message });
    report.checks.push({ label: "library-backup-roundtrip", status: "failed", message });
  } finally {
    await backupContext.close();
  }

  // Phase 2 catalogue sweep: exercise every fragrance detail route once at the
  // primary mobile viewport without multiplying full screenshot artifacts.
  const sweepContext = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 1,
    reducedMotion: "reduce",
  });
  const sweepPage = await sweepContext.newPage();

  try {
    const catalogResponse = await sweepPage.goto(`${baseUrl}/duft`, {
      waitUntil: "domcontentloaded",
      timeout: 45_000,
    });
    if (!catalogResponse || !catalogResponse.ok()) {
      throw new Error(
        `catalog sweep could not open /duft: HTTP ${catalogResponse?.status() ?? "no response"}`,
      );
    }

    for (let step = 0; step < 4; step += 1) {
      const loadMore = sweepPage.getByRole("button", {
        name: /Weitere \d+ Düfte anzeigen/,
      });
      if ((await loadMore.count()) === 0) break;
      await loadMore.click();
      await sweepPage.waitForTimeout(75);
    }

    const detailRoutes = await sweepPage
      .locator('a[href^="/duft/"]')
      .evaluateAll((links) =>
        Array.from(
          new Set(
            links
              .map((link) => link.getAttribute("href"))
              .filter(
                (href) =>
                  typeof href === "string" &&
                  href.startsWith("/duft/"),
              ),
          ),
        ).sort(),
      );

    if (detailRoutes.length !== expectedFragranceCount) {
      throw new Error(
        `catalog sweep expected ${expectedFragranceCount} fragrance routes, got ${detailRoutes.length}`,
      );
    }

    for (const route of detailRoutes) {
      const slug = route.replace(/^\/duft\//, "");
      const label = `detail-sweep-${slug}-390`;
      const url = `${baseUrl}${route}`;

      try {
        const response = await sweepPage.goto(url, {
          waitUntil: "domcontentloaded",
          timeout: 45_000,
        });
        if (!response || !response.ok()) {
          throw new Error(`HTTP ${response?.status() ?? "no response"}`);
        }

        await sweepPage.locator("h1").first().waitFor({
          state: "visible",
          timeout: 20_000,
        });

        await sweepPage.evaluate(async () => {
          const step = Math.max(
            320,
            Math.floor(window.innerHeight * 0.75),
          );
          for (
            let y = 0;
            y < document.documentElement.scrollHeight;
            y += step
          ) {
            window.scrollTo(0, y);
            await new Promise((resolve) => setTimeout(resolve, 20));
          }
          window.scrollTo(0, 0);

          const images = Array.from(document.images).filter((image) => {
            const style = window.getComputedStyle(image);
            return (
              image.getAttribute("src") &&
              style.display !== "none" &&
              style.visibility !== "hidden"
            );
          });
          await Promise.all(
            images.map(async (image) => {
              image.loading = "eager";
              try {
                await image.decode();
              } catch {
                // Broken-image diagnostics below report failed loads.
              }
            }),
          );
        });

        const diagnostics = await sweepPage.evaluate((blocked) => {
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
            .map(
              (image) =>
                image.getAttribute("src") || "(missing src)",
            );

          return {
            body_length: bodyText.length,
            horizontal_overflow:
              document.documentElement.scrollWidth - window.innerWidth,
            visible_broken_images: visibleBrokenImages,
            forbidden_ui: blocked.filter((phrase) =>
              bodyText.includes(phrase),
            ),
            directory_listing:
              bodyText.includes("Index of /") ||
              bodyText.includes("Directory listing for"),
          };
        }, forbiddenUi);

        if (diagnostics.body_length < 250) {
          throw new Error(
            `page content unexpectedly short: ${diagnostics.body_length}`,
          );
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
          throw new Error(
            "directory listing detected instead of storefront content",
          );
        }

        const productSchema = await sweepPage.evaluate(() => {
          const schemas = Array.from(
            document.querySelectorAll(
              'script[type="application/ld+json"]',
            ),
          )
            .map((script) => {
              try {
                return JSON.parse(script.textContent || "{}");
              } catch {
                return null;
              }
            })
            .filter(Boolean);

          return (
            schemas.find(
              (schema) => schema?.["@type"] === "Product",
            ) || null
          );
        });

        if (!productSchema) {
          throw new Error(
            "fragrance detail page is missing Product JSON-LD",
          );
        }
        if (!String(productSchema.name || "").trim()) {
          throw new Error(
            "Product JSON-LD has no usable product name",
          );
        }

        report.checks.push({
          label,
          status: "passed",
          ...diagnostics,
        });
      } catch (error) {
        const message =
          error instanceof Error ? error.message : String(error);
        report.failures.push({ label, url, message });
        report.checks.push({
          label,
          status: "failed",
          message,
        });
      }
    }
  } finally {
    await sweepContext.close();
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
