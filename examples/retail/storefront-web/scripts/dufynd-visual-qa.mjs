import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";

import { chromium } from "playwright";
import { verifyPublicShareLinks } from "./public-share-qa.mjs";
import { verifyLibraryClearRecovery } from "./library-clear-qa.mjs";
import { verifyLibrarySaveRecovery } from "./library-save-qa.mjs";
import { verifyLibraryReadRecovery } from "./library-read-recovery-qa.mjs";
import { verifyLibraryImportReadFailure } from "./library-import-read-qa.mjs";
import { verifyLibraryExportCurrent } from "./library-export-current-qa.mjs";
import { verifyLibraryReadFeedback } from "./library-read-feedback-qa.mjs";
import { verifyFooterNavigationAttribution } from "./footer-navigation-attribution-qa.mjs";
import { verifyErrorRecoveryNavigationAttribution } from "./error-recovery-navigation-qa.mjs";
import { verifyAnalyticsEventTimeout } from "./analytics-event-timeout-qa.mjs";
import { verifyManualShareFallback } from "./manual-share-qa.mjs";
import { verifyLatestProductShare } from "./product-share-race-qa.mjs";
import { verifyCurrentLibraryImport } from "./library-import-current-qa.mjs";
import { verifyLatestLibraryImport } from "./library-import-latest-qa.mjs";
import { verifySocialSearchDismissal } from "./social-search-dismissal-qa.mjs";
import { verifySocialSearchAttribution } from "./social-search-attribution-qa.mjs";
import { verifySocialCatalogNavigation } from "./social-catalog-navigation-qa.mjs";
import { verifyAcquisitionLandingNavigation } from "./acquisition-landing-navigation-qa.mjs";
import { verifyHomeCatalogHydration } from "./home-catalog-hydration-qa.mjs";
import { verifyHomeNavigationAttribution } from "./home-navigation-attribution-qa.mjs";
import { verifyLibraryNavigationAttribution } from "./library-navigation-attribution-qa.mjs";
import { verifyGuidedStartContext } from "./guided-start-context-qa.mjs";
import { verifyGuidedLinkAttribution } from "./guided-link-attribution-qa.mjs";
import { verifyProductDetailRecovery, verifySingleResponsiveProductDetail, verifyClosedProductDetailFocus } from "./product-detail-recovery-qa.mjs";

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
const audienceKeys = ["men", "women", "unisex"];

function exclusiveAudience(product) {
  const groups = new Set(
    (product?.classification?.scentai_target_groups || [])
      .map((group) => String(group || "").trim().toLowerCase())
      .filter(Boolean),
  );

  if (groups.has("unisex")) return "unisex";
  if (groups.has("men") && groups.has("women")) return "unisex";
  if (groups.has("women")) return "women";
  if (groups.has("men")) return "men";
  return null;
}

const expectedAudienceRoutes = Object.fromEntries(
  audienceKeys.map((audience) => [
    audience,
    sourceCatalog.products
      .filter(
        (product) =>
          String(product?.product_id || "").startsWith("SC-") &&
          !hasValidationBlockers(product) &&
          exclusiveAudience(product) === audience,
      )
      .map(
        (product) =>
          "/duft/" +
          slugifyFragrance(
            String(product?.brand || "").trim() +
              " " +
              String(product?.name || "").trim(),
          ),
      )
      .sort(),
  ]),
);

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

function verifiedProductTruthVisual(product) {
  const expectedVariant = `${Number(product?.volume_ml || 0)}ml`.toLowerCase();
  return (product?.visuals || []).find((visual) => {
    const role = String(visual?.role || "");
    const fidelity = String(visual?.fidelity_status || "");
    const variant = String(visual?.variant || "")
      .replace(/\s+/g, "")
      .toLowerCase();
    return (
      (role === "primary" || role === "cutout") &&
      fidelity === "verified" &&
      variant === expectedVariant &&
      String(visual?.url || "").trim()
    );
  });
}

const verifiedTruthByRoute = new Map(
  sourceCatalog.products
    .filter(
      (product) =>
        String(product?.product_id || "").startsWith("SC-") &&
        !hasValidationBlockers(product),
    )
    .map((product) => {
      const route = `/duft/${slugifyFragrance(
        `${String(product?.brand || "").trim()} ${String(product?.name || "").trim()}`,
      )}`;
      return [route, verifiedProductTruthVisual(product)];
    })
    .filter(([, visual]) => Boolean(visual)),
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
  {
    name: "rabanne-1-million",
    route: "/duft/rabanne-1-million",
    marker: "1 Million",
  },
  {
    name: "la-vie-est-belle",
    route: "/duft/lancome-la-vie-est-belle",
    marker: "La Vie est Belle",
  },
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
  try {
    const cases = await verifyHomeCatalogHydration(browser, baseUrl);
    report.checks.push({ label: "home-catalog-hydration", status: "passed", cases });
  } catch (error) {
    report.failures.push({ label: "home-catalog-hydration", message: String(error) });
  }
  try {
    const cases = await verifyFooterNavigationAttribution(browser, baseUrl);
    report.checks.push({ label: "footer-navigation-attribution", status: "passed", cases });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    report.failures.push({ label: "footer-navigation-attribution", message });
  }
  try {
    const cases = await verifyErrorRecoveryNavigationAttribution(browser, baseUrl);
    report.checks.push({ label: "error-recovery-navigation-attribution", status: "passed", cases });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    report.failures.push({ label: "error-recovery-navigation-attribution", message });
  }
  try {
    const cases = await verifyLibraryNavigationAttribution(browser, baseUrl);
    report.checks.push({ label: "library-navigation-attribution", status: "passed", cases });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    report.failures.push({ label: "library-navigation-attribution", message });
  }
  try {
    const cases = await verifyHomeNavigationAttribution(browser, baseUrl);
    report.checks.push({ label: "home-navigation-attribution", status: "passed", cases });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    report.failures.push({ label: "home-navigation-attribution", message });
  }
  try {
    await verifyAcquisitionLandingNavigation(browser, baseUrl);
    report.checks.push({ label: "acquisition-landing-navigation-attribution", status: "passed" });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    report.failures.push({ label: "acquisition-landing-navigation-attribution", message });
  }
  try {
    await verifySocialCatalogNavigation(browser, baseUrl);
    report.checks.push({ label: "social-catalog-navigation-attribution", status: "passed" });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    report.failures.push({ label: "social-catalog-navigation-attribution", message });
  }
  try {
    await verifySocialSearchAttribution(browser, baseUrl);
    report.checks.push({ label: "social-search-attribution-handoff", status: "passed" });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    report.failures.push({ label: "social-search-attribution-handoff", message });
  }
  try {
    await verifyGuidedLinkAttribution(browser, baseUrl);
    report.checks.push({ label: "guided-link-attribution-handoff", status: "passed" });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    report.failures.push({ label: "guided-link-attribution-handoff", message });
  }
  try {
    await verifyGuidedStartContext(browser, baseUrl);
    report.checks.push({ label: "guided-start-url-context", status: "passed" });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    report.failures.push({ label: "guided-start-url-context", message });
  }
  try {
    await verifySocialSearchDismissal(browser, baseUrl);
    report.checks.push({ label: "social-search-keyboard-dismissal", status: "passed" });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    report.failures.push({ label: "social-search-keyboard-dismissal", message });
  }
  try {
    await verifyLatestLibraryImport(browser, baseUrl);
    report.checks.push({ label: "library-import-latest-selection", status: "passed" });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    report.failures.push({ label: "library-import-latest-selection", message });
  }
  try {
    await verifyCurrentLibraryImport(browser, baseUrl);
    report.checks.push({ label: "library-import-current-replacement", status: "passed" });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    report.failures.push({ label: "library-import-current-replacement", message });
  }
  try {
    await verifyLatestProductShare(browser, baseUrl);
    report.checks.push({ label: "product-share-latest-attempt", status: "passed" });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    report.failures.push({ label: "product-share-latest-attempt", message });
  }
  try {
    await verifyManualShareFallback(browser, baseUrl);
    report.checks.push({ label: "manual-share-session-isolation", status: "passed" });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    report.failures.push({ label: "manual-share-session-isolation", message });
  }
  try {
    await verifyAnalyticsEventTimeout(browser, baseUrl);
    report.checks.push({ label: "analytics-event-post-timeout-recovery", status: "passed" });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    report.failures.push({ label: "analytics-event-post-timeout-recovery", message });
  }
  try {
    const cases = await verifyLibraryReadFeedback(browser, baseUrl);
    report.checks.push({ label: "library-read-failure-feedback", status: "passed", cases });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    report.failures.push({ label: "library-read-failure-feedback", message });
  }
  try {
    const cases = await verifyLibraryExportCurrent(browser, baseUrl);
    report.checks.push({ label: "library-export-current-read", status: "passed", cases });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    report.failures.push({ label: "library-export-current-read", message });
  }
  try {
    const cases = await verifyLibraryImportReadFailure(browser, baseUrl);
    report.checks.push({ label: "library-import-read-confirmation", status: "passed", cases });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    report.failures.push({ label: "library-import-read-confirmation", message });
  }
  try {
    const cases = await verifyLibraryReadRecovery(browser, baseUrl);
    report.checks.push({ label: "library-save-read-recovery", status: "passed", cases });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    report.failures.push({ label: "library-save-read-recovery", message });
  }
  try {
    await verifyLibrarySaveRecovery(browser, baseUrl);
    report.checks.push({ label: "library-save-storage-recovery", status: "passed" });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    report.failures.push({ label: "library-save-storage-recovery", message });
  }
  try {
    await verifyLibraryClearRecovery(browser, baseUrl);
    report.checks.push({ label: "library-clear-storage-recovery", status: "passed" });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    report.failures.push({ label: "library-clear-storage-recovery", message });
  }
  try {
    await verifyPublicShareLinks(browser, baseUrl);
    report.checks.push({ label: "public-share-session-isolation-390", status: "passed" });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    report.failures.push({ label: "public-share-session-isolation-390", message });
  }
  try {
    await verifyProductDetailRecovery(browser, baseUrl);
    await verifySingleResponsiveProductDetail(browser, baseUrl);
    await verifyClosedProductDetailFocus(browser, baseUrl);
    report.checks.push({ label: "advisor-product-detail-recovery-390", status: "passed" });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    report.failures.push({ label: "advisor-product-detail-recovery-390", message });
  }
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
        if (
          (await page.locator(".dufynd-product-placeholder").count()) > 0
        ) {
          throw new Error(
            "legacy pseudo-bottle placeholder is still rendered",
          );
        }

        if (target.route.startsWith("/duft/")) {
          const layout = await page.evaluate(() => {
            const rect = (selector) =>
              document.querySelector(selector)?.getBoundingClientRect() || null;
            const title = rect(".dufynd-fragrance-hero h1");
            const stage = rect(".dufynd-fragrance-hero .dufynd-product-stage, .dufynd-fragrance-hero .dufynd-editorial-depth-stage, .dufynd-fragrance-hero .dufynd-model-stage, .dufynd-fragrance-hero .dufynd-neutral-visual-stage");
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

          const expectedTruthVisual = verifiedTruthByRoute.get(target.route);
          if (expectedTruthVisual) {
            if (
              !schemaImages.some((image) =>
                String(image).endsWith(String(expectedTruthVisual.url)),
              )
            ) {
              throw new Error(
                `verified Product JSON-LD does not use the expected product-truth visual: ${expectedTruthVisual.url}`,
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
            "bois-imperial",
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
            'a[href*="/duft/xerjoff-naxos"] img[src="/products/naxos-cutout-production.webp"]',
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
          if ((await page.locator("a").evaluateAll((links) => links.filter((link) =>
            new URL(link.href).pathname === "/duft",
          ).length)) < 1) {
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
          const socialSearch = page.getByRole("searchbox", {
            name: "Duft oder Marke suchen",
          });
          if ((await socialSearch.count()) !== 1) {
            throw new Error("social start is missing direct fragrance search");
          }
          const socialSearchForm = page.locator(
            'form[action="/duft"][method="get"] input[name="q"]',
          );
          if ((await socialSearchForm.count()) !== 1) {
            throw new Error(
              "social start direct search does not target the catalogue query flow",
            );
          }
          await socialSearch.fill("1 Million");
          const directOneMillion = page.locator(
            '[data-dufynd-social-live-results] a',
          );
          if ((await directOneMillion.evaluateAll((links) => links.filter((link) =>
            new URL(link.href).pathname === "/duft/rabanne-1-million",
          ).length)) !== 1) {
            throw new Error(
              "social start live search does not surface Rabanne 1 Million directly",
            );
          }
          await socialSearch.fill("");

          const requiredEntryPaths = [
            "/duftfinder",
            "/duft",
            "/parfum-alternativen",
            "/parfum-geschenkberater",
          ];
          for (const href of requiredEntryPaths) {
            if ((await page.locator("a").evaluateAll((links, path) => links.filter((link) =>
              new URL(link.href).pathname === path,
            ).length, href)) < 1) {
              throw new Error(`social start is missing entry path: ${href}`);
            }
          }

          if ((await page.locator('img[src="/icon.svg"]').count()) < 1) {
            throw new Error("social start is missing the DUFYND brand mark");
          }
        }

        if (target.name === "home") {
          const audienceStage = page.locator(
            "[data-dufynd-home-audience-stage]",
          );
          const audienceCards = page.locator(
            "[data-dufynd-home-audience-card]",
          );
          const selectedStage = page.locator(
            "[data-dufynd-home-selected-stage]",
          );

          if ((await audienceStage.count()) !== 1) {
            throw new Error("homepage is missing immersive audience discovery");
          }
          if ((await audienceCards.count()) !== 3) {
            throw new Error(
              `homepage audience discovery expected 3 cards, got ${await audienceCards.count()}`,
            );
          }

          for (const audience of audienceKeys) {
            const card = page.locator(
              `a[data-dufynd-home-audience-card][href*="zielgruppe=${audience}"]`,
            );
            if ((await card.count()) !== 1) {
              throw new Error(
                `homepage audience card missing for ${audience}`,
              );
            }
            const destination = new URL(await card.getAttribute("href"), baseUrl);
            if (destination.pathname !== "/duft" || destination.searchParams.get("zielgruppe") !== audience) {
              throw new Error(`homepage audience destination mismatch for ${audience}`);
            }

            const expectedCount = expectedAudienceRoutes[audience].length;
            const expectedText =
              expectedCount === 1
                ? "1 Duft im aktuellen Katalog"
                : `${expectedCount} Düfte im aktuellen Katalog`;
            if (!(await card.innerText()).includes(expectedText)) {
              throw new Error(
                `homepage audience count mismatch for ${audience}: expected "${expectedText}"`,
              );
            }
          }
          report.checks.push({
            label: "home-audience-visible-counts",
            status: "passed",
            counts: Object.fromEntries(
              audienceKeys.map((audience) => [
                audience,
                expectedAudienceRoutes[audience].length,
              ]),
            ),
          });

          if ((await selectedStage.count()) !== 1) {
            throw new Error("homepage is missing immersive selected fragrances");
          }

          const invalidWorldCards = await audienceCards.evaluateAll((cards) =>
            cards
              .map((card) => card.getAttribute("data-dufynd-home-world"))
              .filter(
                (world) =>
                  !["amber", "mineral", "ember", "silk", "noir"].includes(
                    String(world),
                  ),
              ),
          );
          if (invalidWorldCards.length) {
            throw new Error(
              `homepage has invalid DUFYND visual worlds: ${invalidWorldCards.join(", ")}`,
            );
          }

          const spotlightTruth = page.locator(
            'a.dufynd-hero-product img[src="/products/naxos-cutout-production.webp"]',
          );
          if ((await spotlightTruth.count()) < 1) {
            throw new Error(
              "homepage spotlight does not prioritize the Naxos verified cutout",
            );
          }
          const spotlightHref = await spotlightTruth.first().evaluate((image) => image.closest("a")?.href);
          if (!spotlightHref || new URL(spotlightHref, baseUrl).pathname !== "/duft/xerjoff-naxos") {
            throw new Error("homepage spotlight does not open Naxos");
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

  const audienceContext = await browser.newContext({
    viewport: { width: 768, height: 1024 },
    deviceScaleFactor: 1,
    reducedMotion: "reduce",
  });
  try {
    const audiencePage = await audienceContext.newPage();
    const actualRoutesByAudience = {};

    for (const audience of audienceKeys) {
      const label =
        audience === "men" ? "Herren" : audience === "women" ? "Damen" : "Unisex";
      const response = await audiencePage.goto(
        baseUrl + "/duft?zielgruppe=" + audience,
        { waitUntil: "networkidle", timeout: 45_000 },
      );
      if (!response?.ok()) {
        throw new Error(
          "catalog audience " + audience +
            " did not load: HTTP " +
            String(response?.status() ?? "no response"),
        );
      }

      const audienceButton = audiencePage.getByRole("button", {
        name: label,
        exact: true,
      });
      await audienceButton.waitFor({ state: "visible", timeout: 20_000 });
      if ((await audienceButton.getAttribute("aria-pressed")) !== "true") {
        throw new Error(
          "catalog did not restore the " + audience + " audience filter from the URL",
        );
      }

      for (let step = 0; step < 10; step += 1) {
        const loadMore = audiencePage.getByRole("button", {
          name: /Weitere \d+ Düfte anzeigen/,
        });
        if ((await loadMore.count()) === 0) break;
        await loadMore.click();
        await audiencePage.waitForTimeout(75);
      }

      const actualRoutes = await audiencePage
        .locator('article.dufynd-catalog-card a')
        .evaluateAll((links) =>
          Array.from(
            new Set(
              links
                .map((link) => new URL(link.href).pathname)
                .filter(
                  (href) =>
                    typeof href === "string" &&
                    href.startsWith("/duft/"),
                ),
            ),
          ).sort(),
        );

      const expectedRoutes = expectedAudienceRoutes[audience];
      if (JSON.stringify(actualRoutes) !== JSON.stringify(expectedRoutes)) {
        const missing = expectedRoutes.filter(
          (route) => !actualRoutes.includes(route),
        );
        const unexpected = actualRoutes.filter(
          (route) => !expectedRoutes.includes(route),
        );
        throw new Error(
          "catalog audience " + audience +
            " mismatch; missing=" + (missing.join(", ") || "none") +
            "; unexpected=" + (unexpected.join(", ") || "none"),
        );
      }

      actualRoutesByAudience[audience] = actualRoutes;
      report.checks.push({
        label: "catalog-audience-" + audience,
        status: "passed",
        count: actualRoutes.length,
      });
    }

    const seenAudienceByRoute = new Map();
    for (const audience of audienceKeys) {
      for (const route of actualRoutesByAudience[audience] || []) {
        const previous = seenAudienceByRoute.get(route);
        if (previous) {
          throw new Error(
            "catalog audience overlap detected for " + route +
              ": " + previous + " and " + audience,
          );
        }
        seenAudienceByRoute.set(route, audience);
      }
    }

    if (seenAudienceByRoute.size !== expectedFragranceCount) {
      throw new Error(
        "exclusive audience coverage expected " + expectedFragranceCount +
          " routes, got " + seenAudienceByRoute.size,
      );
    }

    report.checks.push({
      label: "catalog-audience-exclusive",
      status: "passed",
      count: seenAudienceByRoute.size,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    report.failures.push({
      label: "catalog-audience-exclusive",
      message,
    });
    report.checks.push({
      label: "catalog-audience-exclusive",
      status: "failed",
      message,
    });
  } finally {
    await audienceContext.close();
  }
  const mobileCatalogFilterContext = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 1,
    reducedMotion: "reduce",
  });
  try {
    const mobileCatalogPage = await mobileCatalogFilterContext.newPage();
    const response = await mobileCatalogPage.goto(
      baseUrl + "/duft?utm_source=qa",
      { waitUntil: "networkidle", timeout: 45_000 },
    );
    if (!response?.ok()) {
      throw new Error(
        "mobile catalog filter QA did not load: HTTP " +
          String(response?.status() ?? "no response"),
      );
    }

    const stickyFilterButton = mobileCatalogPage.getByRole("button", {
      name: "Katalogfilter öffnen",
    });
    await stickyFilterButton.waitFor({ state: "visible", timeout: 20_000 });
    await stickyFilterButton.click();

    const filterPanel = mobileCatalogPage.locator("#catalog-filter-panel");
    await filterPanel.waitFor({ state: "visible", timeout: 10_000 });

    const unisexButton = filterPanel.getByRole("button", {
      name: "Unisex",
      exact: true,
    });
    await unisexButton.click();
    await mobileCatalogPage.waitForFunction(() => {
      const url = new URL(window.location.href);
      return (
        url.searchParams.get("zielgruppe") === "unisex" &&
        url.searchParams.get("utm_source") === "qa"
      );
    });

    if ((await unisexButton.getAttribute("aria-pressed")) !== "true") {
      throw new Error("mobile catalog did not activate the Unisex filter");
    }

    const resultSummary = await mobileCatalogPage
      .locator('[aria-live="polite"]')
      .filter({ hasText: /von \d+ Düften/ })
      .first()
      .textContent();
    if (!resultSummary || !/\d+\s+von\s+\d+\s+Düften/.test(resultSummary)) {
      throw new Error("mobile catalog did not expose an updated result count");
    }

    await mobileCatalogPage
      .getByRole("button", { name: "Filter zurücksetzen", exact: true })
      .click();
    await mobileCatalogPage.waitForFunction(() => {
      const url = new URL(window.location.href);
      return (
        !url.searchParams.has("zielgruppe") &&
        url.searchParams.get("utm_source") === "qa"
      );
    });

    if ((await unisexButton.getAttribute("aria-pressed")) === "true") {
      throw new Error("mobile catalog reset left the Unisex filter active");
    }

    report.checks.push({
      label: "catalog-mobile-filter-interaction",
      status: "passed",
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    report.failures.push({
      label: "catalog-mobile-filter-interaction",
      message,
    });
    report.checks.push({
      label: "catalog-mobile-filter-interaction",
      status: "failed",
      message,
    });
  } finally {
    await mobileCatalogFilterContext.close();
  }

  const imageFailureContext = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 1,
    reducedMotion: "reduce",
  });
  try {
    const imageFailurePage = await imageFailureContext.newPage();
    let failPrimaryImage = true;
    let failBackdropImage = false;
    await imageFailurePage.route("**/products/naxos-cutout-production.webp", (route) =>
      failPrimaryImage ? route.abort("failed") : route.continue(),
    );
    await imageFailurePage.route("**/products/naxos-bottle-free-backdrop.webp", (route) =>
      failBackdropImage ? route.abort("failed") : route.continue(),
    );
    const response = await imageFailurePage.goto(baseUrl + "/duft/xerjoff-naxos", {
      waitUntil: "domcontentloaded", timeout: 45_000,
    });
    if (!response?.ok()) throw new Error("image failure QA did not load");
    const hero = imageFailurePage.locator(".dufynd-fragrance-hero");
    const fallback = hero.locator('[data-dufynd-visual-state="unavailable"]');
    await fallback.waitFor({ state: "visible", timeout: 10_000 });
    if (
      !(await fallback.innerText()).includes("Produktbild derzeit nicht verfügbar") ||
      !(await fallback.innerText()).includes("Naxos") ||
      (await hero.locator("img").count()) !== 0
    ) {
      throw new Error("failed product image did not preserve identity in a neutral fallback");
    }
    if ((await imageFailurePage.locator("#angebote").count()) !== 1) {
      throw new Error("image failure removed the merchant offer section");
    }
    failPrimaryImage = false;
    await imageFailurePage.reload({ waitUntil: "domcontentloaded", timeout: 45_000 });
    const recoveredImage = hero.locator("img.dufynd-product-image");
    await recoveredImage.waitFor({ state: "visible", timeout: 10_000 });
    await imageFailurePage.waitForFunction(() => {
      const image = document.querySelector(".dufynd-fragrance-hero img.dufynd-product-image");
      return image?.complete && image.naturalWidth > 0;
    }, undefined, { timeout: 10_000 });
    if ((await fallback.count()) !== 0) {
      throw new Error("successful image retry retained its error fallback");
    }
    failBackdropImage = true;
    await imageFailurePage.reload({ waitUntil: "domcontentloaded", timeout: 45_000 });
    await recoveredImage.waitFor({ state: "visible", timeout: 10_000 });
    await imageFailurePage.waitForFunction(() => {
      const hero = document.querySelector(".dufynd-fragrance-hero");
      const image = hero?.querySelector("img.dufynd-product-image");
      return image?.complete && image.naturalWidth > 0 &&
        !hero.querySelector("img.dufynd-product-backdrop");
    }, undefined, { timeout: 10_000 });
    if ((await fallback.count()) !== 0) {
      throw new Error("decorative backdrop failure hid the valid product image");
    }
    report.checks.push({ label: "product-image-error-fallback", status: "passed" });
    report.checks.push({ label: "product-image-error-recovery", status: "passed" });
    report.checks.push({ label: "decorative-image-error-isolation", status: "passed" });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    report.failures.push({ label: "product-image-error-fallback", message });
    report.checks.push({ label: "product-image-error-fallback", status: "failed", message });
  } finally {
    await imageFailureContext.close();
  }

  const merchantOfferTimeoutContext = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 1,
    reducedMotion: "reduce",
  });
  try {
    const merchantOfferTimeoutPage = await merchantOfferTimeoutContext.newPage();
    let merchantOfferRequestCount = 0;

    await merchantOfferTimeoutPage.route("**/api/session", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          session_id: "qa-merchant-offer-timeout-session-1234567890",
        }),
      });
    });

    await merchantOfferTimeoutPage.route(
      "**/api/analytics/events",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ ok: true }),
        });
      },
    );

    await merchantOfferTimeoutPage.route(
      "**/api/merchant-offers/**",
      async (route) => {
        merchantOfferRequestCount += 1;

        if (merchantOfferRequestCount === 1) {
          await new Promise((resolve) => setTimeout(resolve, 8_500));
          try {
            await route.fulfill({
              status: 200,
              contentType: "application/json",
              body: JSON.stringify({
                product_id: "SC-QA-TIMEOUT-LATE",
                best_offer_id: null,
                offers: [],
                affiliate_disclosure: "Late QA fixture",
              }),
            });
          } catch {
            // The storefront is expected to abort this deliberately slow request.
          }
          return;
        }

        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            product_id: "SC-QA-TIMEOUT-RECOVERY",
            best_offer_id: "qa-timeout-recovery-offer",
            offers: [
              {
                offer_id: "qa-timeout-recovery-offer",
                product_id: "SC-QA-TIMEOUT-RECOVERY",
                merchant_id: "qa-timeout-merchant",
                merchant_name: "QA Timeout Merchant",
                merchant_product_id: "qa-timeout-sku",
                price: 99,
                currency: "EUR",
                shipping_cost: 0,
                shipping_label: "Versand inklusive",
                total_price: 99,
                in_stock: true,
                variant_label: "QA Recovery",
                clickout_path: "/api/clickout/qa-timeout-recovery-offer",
                affiliate_link: false,
                last_updated_at: "2026-09-30T12:00:00Z",
              },
            ],
            affiliate_disclosure: "QA recovery fixture",
          }),
        });
      },
    );

    const response = await merchantOfferTimeoutPage.goto(
      baseUrl + "/duft/rabanne-1-million",
      { waitUntil: "domcontentloaded", timeout: 45_000 },
    );
    if (!response?.ok()) {
      throw new Error(
        "merchant-offer timeout QA did not load: HTTP " +
          String(response?.status() ?? "no response"),
      );
    }

    await merchantOfferTimeoutPage
      .getByText("Händlerangebote werden geprüft …", { exact: true })
      .waitFor({ state: "visible", timeout: 5_000 });

    const retry = merchantOfferTimeoutPage.getByRole("button", {
      name: "Angebote erneut prüfen",
      exact: true,
    });
    await retry.waitFor({ state: "visible", timeout: 12_000 });

    const errorCopy = merchantOfferTimeoutPage.getByText(
      "Die Händlerangebote konnten gerade nicht geladen werden.",
      { exact: false },
    );
    if (!(await errorCopy.isVisible())) {
      throw new Error(
        "merchant-offer timeout did not surface the existing fail-open recovery state",
      );
    }

    await retry.click();

    const recoveredOffers = merchantOfferTimeoutPage.locator(
      "[data-merchant-offers]",
    );
    await recoveredOffers.waitFor({ state: "visible", timeout: 10_000 });
    await recoveredOffers
      .getByText("QA Timeout Merchant", { exact: true })
      .waitFor({ state: "visible", timeout: 5_000 });

    if (merchantOfferRequestCount !== 2) {
      throw new Error(
        "merchant-offer timeout retry expected 2 requests, got " +
          String(merchantOfferRequestCount),
      );
    }

    report.checks.push({
      label: "merchant-offer-request-timeout",
      status: "passed",
    });
    report.checks.push({
      label: "merchant-offer-timeout-recovery",
      status: "passed",
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    report.failures.push({
      label: "merchant-offer-request-timeout",
      message,
    });
    report.checks.push({
      label: "merchant-offer-request-timeout",
      status: "failed",
      message,
    });
  } finally {
    await merchantOfferTimeoutContext.close();
  }

  const analyticsSessionTimeoutContext = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 1,
    reducedMotion: "reduce",
  });
  try {
    const sessionTimeoutPage = await analyticsSessionTimeoutContext.newPage();
    let sessionTimeoutRequestCount = 0;
    let sessionRecoveryAllowed = false;
    const recoveredSessionId = "qa-analytics-timeout-recovery-session-1234567890";

    await sessionTimeoutPage.route("**/api/session", async (route) => {
      sessionTimeoutRequestCount += 1;
      if (sessionRecoveryAllowed) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ session_id: recoveredSessionId, name: "QA Guest" }),
        });
        return;
      }
      if (sessionTimeoutRequestCount === 1) {
        await new Promise((resolve) => setTimeout(resolve, 8_500));
        try {
          await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({ session_id: "qa-stale-late-session", name: "Late QA Guest" }),
          });
        } catch {
          // The client must discard the late result of an aborted session request.
        }
        return;
      }
      await route.abort("failed");
    });
    await sessionTimeoutPage.route("**/api/analytics/events", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: '{"ok":true}' }),
    );
    await sessionTimeoutPage.route("**/api/merchant-offers/**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          product_id: "SC-QA-SESSION-TIMEOUT",
          best_offer_id: "qa-session-timeout-offer",
          offers: [{
            offer_id: "qa-session-timeout-offer",
            merchant_name: "QA Session Timeout Merchant",
            price: 99,
            total_price: 99,
            currency: "EUR",
            clickout_path: "/api/clickout/qa-session-timeout-offer",
            affiliate_link: false,
            last_updated_at: "2026-09-30T12:00:00Z",
          }],
        }),
      }),
    );
    const response = await sessionTimeoutPage.goto(
      baseUrl + "/duft/rabanne-1-million?src=tiktok&cmp=qa_session_timeout&content=qa_session_timeout_content",
      { waitUntil: "domcontentloaded", timeout: 45_000 },
    );
    if (!response?.ok()) throw new Error("session timeout QA did not load");
    const offers = sessionTimeoutPage.locator("[data-merchant-offers]");
    await offers.waitFor({ state: "visible", timeout: 5_000 });
    await offers.locator("[data-clickout-preparing]").waitFor({
      state: "visible", timeout: 5_000,
    });
    const clickout = offers.getByRole("link", { name: "Bei QA Session Timeout Merchant ansehen" });
    await clickout.waitFor({ state: "visible", timeout: 12_000 });
    await new Promise((resolve) => setTimeout(resolve, 750));
    const failOpenUrl = new URL(await clickout.getAttribute("href"));
    if (
      failOpenUrl.searchParams.has("sid") ||
      failOpenUrl.searchParams.get("src") !== "tiktok" ||
      failOpenUrl.searchParams.get("cmp") !== "qa_session_timeout" ||
      failOpenUrl.searchParams.get("content") !== "qa_session_timeout_content"
    ) {
      throw new Error("session timeout fail-open installed a stale session or lost attribution");
    }
    if ((await offers.locator("[data-clickout-preparing]").count()) !== 0) {
      throw new Error("stalled session kept a loaded merchant offer blocked");
    }
    sessionRecoveryAllowed = true;
    await sessionTimeoutPage.reload({ waitUntil: "domcontentloaded", timeout: 45_000 });
    await clickout.waitFor({ state: "visible", timeout: 10_000 });
    const recoveredUrl = new URL(await clickout.getAttribute("href"));
    if (
      recoveredUrl.searchParams.get("sid") !== recoveredSessionId ||
      recoveredUrl.searchParams.get("cmp") !== "qa_session_timeout"
    ) {
      throw new Error("session recovery did not restore first-party correlation");
    }
    report.checks.push({ label: "analytics-session-request-timeout", status: "passed" });
    report.checks.push({ label: "analytics-session-timeout-recovery", status: "passed" });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    report.failures.push({ label: "analytics-session-request-timeout", message });
    report.checks.push({ label: "analytics-session-request-timeout", status: "failed", message });
  } finally {
    await analyticsSessionTimeoutContext.close();
  }

  const attributionClickoutContext = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 1,
    reducedMotion: "reduce",
  });
  try {
    const attributionPage = await attributionClickoutContext.newPage();
    await attributionPage.route(
      "**/api/merchant-offers/**",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            product_id: "SC-QA-ATTRIBUTION",
            best_offer_id: "qa-attribution-offer",
            offers: [
              {
                offer_id: "qa-attribution-offer",
                product_id: "SC-QA-ATTRIBUTION",
                merchant_id: "qa-merchant",
                merchant_name: "QA Merchant",
                merchant_product_id: "qa-sku",
                price: 99,
                currency: "EUR",
                shipping_cost: 0,
                shipping_label: "Versand inklusive",
                total_price: 99,
                in_stock: true,
                variant_label: "QA",
                clickout_path: "/api/clickout/qa-attribution-offer",
                affiliate_link: false,
                last_updated_at: "2026-09-30T12:00:00Z",
              },
            ],
            affiliate_disclosure: "QA fixture",
          }),
        });
      },
    );
    const response = await attributionPage.goto(
      baseUrl +
        "/duft/rabanne-1-million?src=tiktok&cmp=qa_campaign&content=qa_content",
      { waitUntil: "networkidle", timeout: 45_000 },
    );
    if (!response?.ok()) {
      throw new Error(
        "merchant clickout attribution QA did not load: HTTP " +
          String(response?.status() ?? "no response"),
      );
    }

    const offers = attributionPage.locator("[data-merchant-offers]");
    await offers.waitFor({ state: "visible", timeout: 20_000 });

    const clickout = offers.locator('a[href*="/api/clickout/"]').first();
    await clickout.waitFor({ state: "visible", timeout: 10_000 });

    const href = await clickout.getAttribute("href");
    if (!href) {
      throw new Error("merchant offer is missing its clickout href");
    }

    const clickoutUrl = new URL(href, baseUrl);
    if (!clickoutUrl.pathname.startsWith("/api/clickout/")) {
      throw new Error(
        "merchant offer no longer points at the guarded internal clickout route",
      );
    }
    if (
      clickoutUrl.searchParams.get("src") !== "tiktok" ||
      clickoutUrl.searchParams.get("cmp") !== "qa_campaign" ||
      clickoutUrl.searchParams.get("content") !== "qa_content"
    ) {
      throw new Error(
        "merchant clickout href did not preserve acquisition attribution",
      );
    }

    if ((await clickout.getAttribute("target")) !== "_blank") {
      throw new Error("merchant clickout no longer opens in a separate browsing context");
    }

    report.checks.push({
      label: "merchant-clickout-attribution-link",
      status: "passed",
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    report.failures.push({
      label: "merchant-clickout-attribution-link",
      message,
    });
    report.checks.push({
      label: "merchant-clickout-attribution-link",
      status: "failed",
      message,
    });
  } finally {
    await attributionClickoutContext.close();
  }


  const offerImpressionContext = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 1,
    reducedMotion: "reduce",
  });
  try {
    const offerImpressionPage = await offerImpressionContext.newPage();
    const offerViewEvents = [];

    await offerImpressionPage.route("**/api/session", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          session_id: "qa-offer-impression-session-1234567890",
        }),
      });
    });

    await offerImpressionPage.route(
      "**/api/analytics/events",
      async (route) => {
        try {
          const payload = route.request().postDataJSON();
          if (payload?.event === "offer_section_view") {
            offerViewEvents.push(payload);
          }
        } catch {
          // Non-JSON analytics payloads are irrelevant to this assertion.
        }
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ ok: true }),
        });
      },
    );

    await offerImpressionPage.route(
      "**/api/merchant-offers/**",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            product_id: "SC-QA-OFFER-IMPRESSION",
            best_offer_id: "qa-offer-impression-offer",
            offers: [
              {
                offer_id: "qa-offer-impression-offer",
                product_id: "SC-QA-OFFER-IMPRESSION",
                merchant_id: "qa-merchant",
                merchant_name: "QA Merchant",
                merchant_product_id: "qa-offer-impression-sku",
                price: 99,
                currency: "EUR",
                shipping_cost: 0,
                shipping_label: "Versand inklusive",
                total_price: 99,
                in_stock: true,
                variant_label: "QA Impression",
                clickout_path: "/api/clickout/qa-offer-impression-offer",
                affiliate_link: false,
                last_updated_at: "2026-09-30T12:00:00Z",
              },
            ],
            affiliate_disclosure: "QA fixture",
          }),
        });
      },
    );

    const response = await offerImpressionPage.goto(
      baseUrl +
        "/duft/rabanne-1-million?src=instagram&cmp=qa_offer_campaign&content=qa_offer_content",
      { waitUntil: "domcontentloaded", timeout: 45_000 },
    );
    if (!response?.ok()) {
      throw new Error(
        "offer-section impression QA did not load: HTTP " +
          String(response?.status() ?? "no response"),
      );
    }

    const offers = offerImpressionPage.locator("[data-merchant-offers]");
    await offers.waitFor({ state: "visible", timeout: 20_000 });
    await offers.scrollIntoViewIfNeeded();

    for (let attempt = 0; attempt < 50 && offerViewEvents.length === 0; attempt += 1) {
      await offerImpressionPage.waitForTimeout(100);
    }

    if (offerViewEvents.length !== 1) {
      throw new Error(
        "offer section did not emit exactly one visible impression event",
      );
    }

    const impression = offerViewEvents[0];
    if (
      impression.event !== "offer_section_view" ||
      impression.source !== "merchant_offers" ||
      impression.surface !== "fragrance_detail" ||
      impression.acquisition_source !== "instagram" ||
      impression.campaign_id !== "qa_offer_campaign" ||
      impression.content_id !== "qa_offer_content"
    ) {
      throw new Error(
        "offer-section impression lost conversion or acquisition context",
      );
    }

    await offerImpressionPage.evaluate(() => window.scrollTo(0, 0));
    await offerImpressionPage.waitForTimeout(150);
    await offers.scrollIntoViewIfNeeded();
    await offerImpressionPage.waitForTimeout(250);

    if (offerViewEvents.length !== 1) {
      throw new Error(
        "offer-section impression was emitted more than once for the same product surface",
      );
    }

    report.checks.push({
      label: "offer-section-impression-tracking",
      status: "passed",
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    report.failures.push({
      label: "offer-section-impression-tracking",
      message,
    });
    report.checks.push({
      label: "offer-section-impression-tracking",
      status: "failed",
      message,
    });
  } finally {
    await offerImpressionContext.close();
  }


  const acquisitionNavigationContext = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 1,
    reducedMotion: "reduce",
  });
  try {
    const acquisitionNavigationPage = await acquisitionNavigationContext.newPage();
    await acquisitionNavigationPage.route(
      "**/api/merchant-offers/**",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            product_id: "SC-QA-ATTRIBUTION-NAV",
            best_offer_id: "qa-attribution-nav-offer",
            offers: [
              {
                offer_id: "qa-attribution-nav-offer",
                product_id: "SC-QA-ATTRIBUTION-NAV",
                merchant_id: "qa-merchant",
                merchant_name: "QA Merchant",
                merchant_product_id: "qa-nav-sku",
                price: 99,
                currency: "EUR",
                shipping_cost: 0,
                shipping_label: "Versand inklusive",
                total_price: 99,
                in_stock: true,
                variant_label: "QA Navigation",
                clickout_path: "/api/clickout/qa-attribution-nav-offer",
                affiliate_link: false,
                last_updated_at: "2026-09-30T12:00:00Z",
              },
            ],
            affiliate_disclosure: "QA fixture",
          }),
        });
      },
    );

    const landingResponse = await acquisitionNavigationPage.goto(
      baseUrl +
        "/start?src=tiktok&cmp=qa_navigation_campaign&content=qa_navigation_content",
      { waitUntil: "networkidle", timeout: 45_000 },
    );
    if (!landingResponse?.ok()) {
      throw new Error(
        "acquisition navigation attribution QA did not load /start: HTTP " +
          String(landingResponse?.status() ?? "no response"),
      );
    }

    await acquisitionNavigationPage
      .getByRole("link", { name: "Katalog entdecken", exact: true })
      .click();
    await acquisitionNavigationPage.waitForURL(
      (url) => url.pathname === "/duft",
      { timeout: 20_000 },
    );

    for (let step = 0; step < 4; step += 1) {
      const targetLink = acquisitionNavigationPage.locator(
        'a[href*="/duft/rabanne-1-million"]',
      );
      if ((await targetLink.count()) > 0) {
        await targetLink.first().click();
        break;
      }
      const loadMore = acquisitionNavigationPage.getByRole("button", {
        name: /Weitere \d+ Düfte anzeigen/,
      });
      if ((await loadMore.count()) === 0) break;
      await loadMore.click();
      await acquisitionNavigationPage.waitForTimeout(75);
    }

    await acquisitionNavigationPage.waitForURL(
      (url) => url.pathname === "/duft/rabanne-1-million",
      { timeout: 20_000 },
    );

    const navOffers = acquisitionNavigationPage.locator("[data-merchant-offers]");
    await navOffers.waitFor({ state: "visible", timeout: 20_000 });
    const navClickout = navOffers.locator('a[href*="/api/clickout/"]').first();
    await navClickout.waitFor({ state: "visible", timeout: 10_000 });

    const navHref = await navClickout.getAttribute("href");
    if (!navHref) {
      throw new Error("internally navigated merchant offer is missing its clickout href");
    }

    const navClickoutUrl = new URL(navHref, baseUrl);
    if (
      navClickoutUrl.searchParams.get("src") !== "tiktok" ||
      navClickoutUrl.searchParams.get("cmp") !== "qa_navigation_campaign" ||
      navClickoutUrl.searchParams.get("content") !== "qa_navigation_content"
    ) {
      throw new Error(
        "acquisition attribution was lost across internal storefront navigation",
      );
    }

    report.checks.push({
      label: "acquisition-navigation-clickout-attribution",
      status: "passed",
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    report.failures.push({
      label: "acquisition-navigation-clickout-attribution",
      message,
    });
    report.checks.push({
      label: "acquisition-navigation-clickout-attribution",
      status: "failed",
      message,
    });
  } finally {
    await acquisitionNavigationContext.close();
  }


  const clickoutSessionContext = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 1,
    reducedMotion: "reduce",
  });
  try {
    const clickoutSessionPage = await clickoutSessionContext.newPage();
    const expectedSessionId = "qa-clickout-session-1234567890";

    await clickoutSessionPage.route("**/api/session", async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 1200));
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          session_id: expectedSessionId,
        }),
      });
    });

    await clickoutSessionPage.route(
      "**/api/analytics/events",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ ok: true }),
        });
      },
    );

    await clickoutSessionPage.route(
      "**/api/merchant-offers/**",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            product_id: "SC-QA-SESSION-CORRELATION",
            best_offer_id: "qa-session-correlation-offer",
            offers: [
              {
                offer_id: "qa-session-correlation-offer",
                product_id: "SC-QA-SESSION-CORRELATION",
                merchant_id: "qa-merchant",
                merchant_name: "QA Merchant",
                merchant_product_id: "qa-session-sku",
                price: 99,
                currency: "EUR",
                shipping_cost: 0,
                shipping_label: "Versand inklusive",
                total_price: 99,
                in_stock: true,
                variant_label: "QA Session",
                clickout_path: "/api/clickout/qa-session-correlation-offer",
                affiliate_link: false,
                last_updated_at: "2026-09-30T12:00:00Z",
              },
            ],
            affiliate_disclosure: "QA fixture",
          }),
        });
      },
    );

    const response = await clickoutSessionPage.goto(
      baseUrl +
        "/duft/rabanne-1-million?src=tiktok&cmp=qa_sid_campaign&content=qa_sid_content",
      { waitUntil: "domcontentloaded", timeout: 45_000 },
    );
    if (!response?.ok()) {
      throw new Error(
        "merchant clickout session-correlation QA did not load: HTTP " +
          String(response?.status() ?? "no response"),
      );
    }

    const offers = clickoutSessionPage.locator("[data-merchant-offers]");
    await offers.waitFor({ state: "visible", timeout: 20_000 });

    const preparing = offers.locator("[data-clickout-preparing]").first();
    await preparing.waitFor({ state: "visible", timeout: 5_000 });
    if (
      (await offers.locator('a[href*="/api/clickout/"]').count()) !== 0
    ) {
      throw new Error(
        "merchant clickout became actionable before analytics session correlation completed",
      );
    }

    const clickout = offers.locator('a[href*="/api/clickout/"]').first();
    await clickout.waitFor({ state: "visible", timeout: 10_000 });

    await clickoutSessionPage.waitForFunction(
      ({ selector, sessionId }) => {
        const link = document.querySelector(selector);
        if (!(link instanceof HTMLAnchorElement)) return false;
        const url = new URL(link.href);
        return url.searchParams.get("sid") === sessionId;
      },
      {
        selector:
          '[data-merchant-offers] a[href*="/api/clickout/"]',
        sessionId: expectedSessionId,
      },
      { timeout: 10_000 },
    );

    const href = await clickout.getAttribute("href");
    if (!href) {
      throw new Error(
        "merchant clickout session-correlation QA is missing its href",
      );
    }

    const clickoutUrl = new URL(href, baseUrl);
    if (
      clickoutUrl.searchParams.get("src") !== "tiktok" ||
      clickoutUrl.searchParams.get("cmp") !== "qa_sid_campaign" ||
      clickoutUrl.searchParams.get("content") !== "qa_sid_content" ||
      clickoutUrl.searchParams.get("sid") !== expectedSessionId
    ) {
      throw new Error(
        "merchant clickout did not correlate acquisition and analytics session context",
      );
    }

    report.checks.push({
      label: "merchant-clickout-session-correlation",
      status: "passed",
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    report.failures.push({
      label: "merchant-clickout-session-correlation",
      message,
    });
    report.checks.push({
      label: "merchant-clickout-session-correlation",
      status: "failed",
      message,
    });
  } finally {
    await clickoutSessionContext.close();
  }

  const partnerSessionContext = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 1,
    reducedMotion: "reduce",
  });
  try {
    const partnerSessionPage = await partnerSessionContext.newPage();
    const expectedPartnerSessionId = "qa-partner-session-1234567890";

    await partnerSessionPage.route("**/api/session", async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 1200));
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          session_id: expectedPartnerSessionId,
          name: "QA Guest",
        }),
      });
    });

    await partnerSessionPage.route(
      "**/api/merchant-partners",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            partners: [
              {
                merchant_id: "qa-partner",
                merchant_name: "QA Partner",
                description: "Session correlation fixture",
                clickout_path: "/api/merchant-partners/qa-partner/clickout",
              },
            ],
            affiliate_disclosure: "QA fixture",
          }),
        });
      },
    );

    const response = await partnerSessionPage.goto(
      baseUrl +
        "/?src=instagram&cmp=qa_partner_campaign&content=qa_partner_content",
      { waitUntil: "domcontentloaded", timeout: 45_000 },
    );
    if (!response?.ok()) {
      throw new Error(
        "merchant discovery session-correlation QA did not load: HTTP " +
          String(response?.status() ?? "no response"),
      );
    }

    const discovery = partnerSessionPage.getByRole("region", {
      name: "Partnerhändler entdecken",
    });
    await discovery.waitFor({ state: "visible", timeout: 20_000 });

    const preparing = discovery.locator(
      "[data-partner-clickout-preparing]",
    );
    await preparing.waitFor({ state: "visible", timeout: 5_000 });
    if (
      (await discovery.locator('a[href*="/api/merchant-partners/"]').count()) !== 0
    ) {
      throw new Error(
        "merchant discovery clickout became actionable before storefront session correlation completed",
      );
    }

    const clickout = discovery
      .locator('a[href*="/api/merchant-partners/"]')
      .first();
    await clickout.waitFor({ state: "visible", timeout: 10_000 });

    const href = await clickout.getAttribute("href");
    if (!href) {
      throw new Error(
        "merchant discovery session-correlation QA is missing its href",
      );
    }

    const clickoutUrl = new URL(href, baseUrl);
    if (
      clickoutUrl.searchParams.get("src") !== "instagram" ||
      clickoutUrl.searchParams.get("cmp") !== "qa_partner_campaign" ||
      clickoutUrl.searchParams.get("content") !== "qa_partner_content" ||
      clickoutUrl.searchParams.get("sid") !== expectedPartnerSessionId
    ) {
      throw new Error(
        "merchant discovery clickout did not correlate acquisition and storefront session context",
      );
    }

    report.checks.push({
      label: "merchant-discovery-session-correlation",
      status: "passed",
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    report.failures.push({
      label: "merchant-discovery-session-correlation",
      message,
    });
    report.checks.push({
      label: "merchant-discovery-session-correlation",
      status: "failed",
      message,
    });
  } finally {
    await partnerSessionContext.close();
  }

  const partnerSessionFailureContext = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 1,
    reducedMotion: "reduce",
  });
  try {
    const partnerSessionFailurePage =
      await partnerSessionFailureContext.newPage();

    await partnerSessionFailurePage.route("**/api/session", async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 1200));
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ detail: "QA session unavailable" }),
      });
    });

    await partnerSessionFailurePage.route(
      "**/api/merchant-partners",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            partners: [
              {
                merchant_id: "qa-partner-fallback",
                merchant_name: "QA Partner Fallback",
                description: "Session failure fallback fixture",
                clickout_path:
                  "/api/merchant-partners/qa-partner-fallback/clickout",
              },
            ],
            affiliate_disclosure: "QA fixture",
          }),
        });
      },
    );

    const response = await partnerSessionFailurePage.goto(
      baseUrl +
        "/?src=youtube&cmp=qa_partner_failure&content=qa_partner_failure_content",
      { waitUntil: "domcontentloaded", timeout: 45_000 },
    );
    if (!response?.ok()) {
      throw new Error(
        "merchant discovery session-failure QA did not load: HTTP " +
          String(response?.status() ?? "no response"),
      );
    }

    const discovery = partnerSessionFailurePage.getByRole("region", {
      name: "Partnerhändler entdecken",
    });
    await discovery.waitFor({ state: "visible", timeout: 20_000 });

    const preparing = discovery.locator(
      "[data-partner-clickout-preparing]",
    );
    await preparing.waitFor({ state: "visible", timeout: 5_000 });
    if (
      (await discovery.locator('a[href*="/api/merchant-partners/"]').count()) !== 0
    ) {
      throw new Error(
        "merchant discovery fail-open link became actionable before session initialization settled",
      );
    }

    const clickout = discovery
      .locator('a[href*="/api/merchant-partners/"]')
      .first();
    await clickout.waitFor({ state: "visible", timeout: 10_000 });

    const href = await clickout.getAttribute("href");
    if (!href) {
      throw new Error(
        "merchant discovery session-failure QA is missing its href",
      );
    }

    const clickoutUrl = new URL(href, baseUrl);
    if (
      clickoutUrl.searchParams.get("src") !== "youtube" ||
      clickoutUrl.searchParams.get("cmp") !== "qa_partner_failure" ||
      clickoutUrl.searchParams.get("content") !==
        "qa_partner_failure_content" ||
      clickoutUrl.searchParams.has("sid")
    ) {
      throw new Error(
        "merchant discovery session-failure fallback lost attribution or emitted an invalid sid",
      );
    }

    report.checks.push({
      label: "merchant-discovery-session-failure-fallback",
      status: "passed",
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    report.failures.push({
      label: "merchant-discovery-session-failure-fallback",
      message,
    });
    report.checks.push({
      label: "merchant-discovery-session-failure-fallback",
      status: "failed",
      message,
    });
  } finally {
    await partnerSessionFailureContext.close();
  }

  const partnerLoadRecoveryContext = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 1,
    reducedMotion: "reduce",
  });
  try {
    const partnerLoadRecoveryPage =
      await partnerLoadRecoveryContext.newPage();
    let partnerRequestCount = 0;

    await partnerLoadRecoveryPage.route("**/api/session", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          session_id: "qa-partner-recovery-session-1234567890",
          name: "QA Guest",
        }),
      });
    });

    await partnerLoadRecoveryPage.route(
      "**/api/merchant-partners",
      async (route) => {
        partnerRequestCount += 1;
        if (partnerRequestCount === 1) {
          await new Promise((resolve) => setTimeout(resolve, 1200));
          await route.fulfill({
            status: 503,
            contentType: "application/json",
            body: JSON.stringify({ detail: "QA partner discovery unavailable" }),
          });
          return;
        }

        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            partners: [
              {
                merchant_id: "qa-partner-recovery",
                merchant_name: "QA Partner Recovery",
                description: "Load recovery fixture",
                clickout_path:
                  "/api/merchant-partners/qa-partner-recovery/clickout",
              },
            ],
            affiliate_disclosure: "QA fixture",
          }),
        });
      },
    );

    const response = await partnerLoadRecoveryPage.goto(
      baseUrl + "/?src=instagram&cmp=qa_partner_recovery",
      { waitUntil: "domcontentloaded", timeout: 45_000 },
    );
    if (!response?.ok()) {
      throw new Error(
        "merchant discovery load-recovery QA did not load: HTTP " +
          String(response?.status() ?? "no response"),
      );
    }

    const loading = partnerLoadRecoveryPage.locator(
      "[data-merchant-discovery-loading]",
    );
    await loading.waitFor({ state: "visible", timeout: 5_000 });
    if (
      (await loading.locator('a[href*="/api/merchant-partners/"]').count()) !== 0
    ) {
      throw new Error(
        "merchant discovery loading state exposed an actionable partner link",
      );
    }

    const recovery = partnerLoadRecoveryPage.locator(
      "[data-merchant-discovery-error]",
    );
    await recovery.waitFor({ state: "visible", timeout: 20_000 });
    if ((await loading.count()) !== 0) {
      throw new Error(
        "merchant discovery loading placeholder did not clear after load failure",
      );
    }
    await recovery
      .getByRole("button", { name: "Partnerhändler erneut laden" })
      .click();

    const discovery = partnerLoadRecoveryPage.getByRole("region", {
      name: "Partnerhändler entdecken",
    });
    await discovery
      .getByRole("link", { name: /QA Partner Recovery öffnen/ })
      .waitFor({ state: "visible", timeout: 10_000 });

    if (partnerRequestCount !== 2) {
      throw new Error(
        `merchant discovery retry expected 2 partner requests, got ${partnerRequestCount}`,
      );
    }

    if (
      (await partnerLoadRecoveryPage.locator(
        "[data-merchant-discovery-error]",
      ).count()) !== 0
    ) {
      throw new Error(
        "merchant discovery retry did not clear its recovery state",
      );
    }

    report.checks.push({
      label: "merchant-discovery-loading-stability",
      status: "passed",
    });
    report.checks.push({
      label: "merchant-discovery-load-recovery",
      status: "passed",
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    report.failures.push({
      label: "merchant-discovery-load-recovery",
      message,
    });
    report.checks.push({
      label: "merchant-discovery-load-recovery",
      status: "failed",
      message,
    });
  } finally {
    await partnerLoadRecoveryContext.close();
  }

  const partnerTimeoutRecoveryContext = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 1,
    reducedMotion: "reduce",
  });
  try {
    const partnerTimeoutRecoveryPage =
      await partnerTimeoutRecoveryContext.newPage();
    let partnerTimeoutRequestCount = 0;

    await partnerTimeoutRecoveryPage.route("**/api/session", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          session_id: "qa-partner-timeout-recovery-session-1234567890",
          name: "QA Guest",
        }),
      });
    });

    await partnerTimeoutRecoveryPage.route(
      "**/api/merchant-partners",
      async (route) => {
        partnerTimeoutRequestCount += 1;
        if (partnerTimeoutRequestCount === 1) {
          await new Promise((resolve) => setTimeout(resolve, 8_500));
          try {
            await route.fulfill({
              status: 200,
              contentType: "application/json",
              body: JSON.stringify({ partners: [], affiliate_disclosure: "Late QA fixture" }),
            });
          } catch {
            // The client aborts this deliberately stalled partner request.
          }
          return;
        }

        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            partners: [
              {
                merchant_id: "qa-partner-timeout-recovery",
                merchant_name: "QA Partner Timeout Recovery",
                description: "Timeout recovery fixture",
                clickout_path:
                  "/api/merchant-partners/qa-partner-timeout-recovery/clickout",
              },
            ],
            affiliate_disclosure: "QA fixture",
          }),
        });
      },
    );

    const response = await partnerTimeoutRecoveryPage.goto(
      baseUrl + "/?src=instagram&cmp=qa_partner_timeout_recovery",
      { waitUntil: "domcontentloaded", timeout: 45_000 },
    );
    if (!response?.ok()) {
      throw new Error(
        "merchant discovery timeout-recovery QA did not load: HTTP " +
          String(response?.status() ?? "no response"),
      );
    }

    const loading = partnerTimeoutRecoveryPage.locator(
      "[data-merchant-discovery-loading]",
    );
    await loading.waitFor({ state: "visible", timeout: 5_000 });
    if (
      (await loading.locator('a[href*="/api/merchant-partners/"]').count()) !== 0
    ) {
      throw new Error(
        "merchant discovery loading state exposed an actionable partner link",
      );
    }

    const recovery = partnerTimeoutRecoveryPage.locator(
      "[data-merchant-discovery-error]",
    );
    await recovery.waitFor({ state: "visible", timeout: 12_000 });
    if ((await loading.count()) !== 0) {
      throw new Error(
        "merchant discovery loading placeholder did not clear after load failure",
      );
    }
    await recovery
      .getByRole("button", { name: "Partnerhändler erneut laden" })
      .click();

    const discovery = partnerTimeoutRecoveryPage.getByRole("region", {
      name: "Partnerhändler entdecken",
    });
    await discovery
      .getByRole("link", { name: /QA Partner Timeout Recovery öffnen/ })
      .waitFor({ state: "visible", timeout: 10_000 });

    const recoveredPartner = discovery.getByRole("link", {
      name: /QA Partner Timeout Recovery öffnen/,
    });
    const recoveredUrl = new URL(await recoveredPartner.getAttribute("href"));
    if (
      recoveredUrl.searchParams.get("sid") !== "qa-partner-timeout-recovery-session-1234567890" ||
      recoveredUrl.searchParams.get("src") !== "instagram" ||
      recoveredUrl.searchParams.get("cmp") !== "qa_partner_timeout_recovery"
    ) {
      throw new Error("partner timeout retry lost session or acquisition attribution");
    }
    await new Promise((resolve) => setTimeout(resolve, 750));
    if (!(await recoveredPartner.isVisible())) {
      throw new Error("late aborted partner response replaced the successful retry");
    }

    if (partnerTimeoutRequestCount !== 2) {
      throw new Error(
        `merchant discovery retry expected 2 partner requests, got ${partnerTimeoutRequestCount}`,
      );
    }

    if (
      (await partnerTimeoutRecoveryPage.locator(
        "[data-merchant-discovery-error]",
      ).count()) !== 0
    ) {
      throw new Error(
        "merchant discovery retry did not clear its recovery state",
      );
    }

    report.checks.push({
      label: "merchant-partner-request-timeout",
      status: "passed",
    });
    report.checks.push({
      label: "merchant-partner-timeout-recovery",
      status: "passed",
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    report.failures.push({
      label: "merchant-partner-timeout-recovery",
      message,
    });
    report.checks.push({
      label: "merchant-partner-timeout-recovery",
      status: "failed",
      message,
    });
  } finally {
    await partnerTimeoutRecoveryContext.close();
  }

  const homeSessionTimeoutContext = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 1,
    reducedMotion: "reduce",
  });
  try {
    const homeSessionTimeoutPage = await homeSessionTimeoutContext.newPage();
    let homeSessionRequestCount = 0;
    let homeSessionRecoveryAllowed = false;
    const recoveredHomeSessionId = "qa-home-timeout-recovery-session-1234567890";
    await homeSessionTimeoutPage.route("**/api/session", async (route) => {
      homeSessionRequestCount += 1;
      if (homeSessionRecoveryAllowed) {
        await route.fulfill({
          status: 200, contentType: "application/json",
          body: JSON.stringify({ session_id: recoveredHomeSessionId, name: "QA Guest" }),
        });
        return;
      }
      if (homeSessionRequestCount === 1) {
        await new Promise((resolve) => setTimeout(resolve, 8_500));
        try {
          await route.fulfill({
            status: 200, contentType: "application/json",
            body: JSON.stringify({ session_id: "qa-home-stale-late-session", name: "Late QA Guest" }),
          });
        } catch {
          // Homepage initialization must abort and ignore this late response.
        }
        return;
      }
      await route.abort("failed");
    });
    await homeSessionTimeoutPage.route("**/api/analytics/events", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: '{"ok":true}' }),
    );
    await homeSessionTimeoutPage.route("**/api/merchant-partners", (route) =>
      route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({
          partners: [{
            merchant_id: "qa-home-timeout-partner",
            merchant_name: "QA Home Timeout Partner",
            description: "Session timeout fixture",
            clickout_path: "/api/merchant-partners/qa-home-timeout-partner/clickout",
          }],
          affiliate_disclosure: "QA fixture",
        }),
      }),
    );
    const response = await homeSessionTimeoutPage.goto(
      baseUrl + "/?src=instagram&cmp=qa_home_session_timeout&content=qa_home_session_content",
      { waitUntil: "domcontentloaded", timeout: 45_000 },
    );
    if (!response?.ok()) throw new Error("homepage session timeout QA did not load");
    await homeSessionTimeoutPage.locator("[data-partner-clickout-preparing]").waitFor({
      state: "visible", timeout: 5_000,
    });
    const partnerLink = homeSessionTimeoutPage.getByRole("link", {
      name: /QA Home Timeout Partner öffnen/,
    });
    await partnerLink.waitFor({ state: "visible", timeout: 12_000 });
    await new Promise((resolve) => setTimeout(resolve, 750));
    const failOpenUrl = new URL(await partnerLink.getAttribute("href"));
    if (
      failOpenUrl.searchParams.has("sid") ||
      failOpenUrl.searchParams.get("src") !== "instagram" ||
      failOpenUrl.searchParams.get("cmp") !== "qa_home_session_timeout" ||
      failOpenUrl.searchParams.get("content") !== "qa_home_session_content" ||
      (await homeSessionTimeoutPage.locator("[data-partner-clickout-preparing]").count()) !== 0
    ) {
      throw new Error("homepage session timeout retained a blocked link, stale sid or lost attribution");
    }
    homeSessionRecoveryAllowed = true;
    await homeSessionTimeoutPage.reload({ waitUntil: "domcontentloaded", timeout: 45_000 });
    await partnerLink.waitFor({ state: "visible", timeout: 10_000 });
    const recoveredUrl = new URL(await partnerLink.getAttribute("href"));
    if (
      recoveredUrl.searchParams.get("sid") !== recoveredHomeSessionId ||
      recoveredUrl.searchParams.get("cmp") !== "qa_home_session_timeout"
    ) {
      throw new Error("homepage session recovery lost first-party correlation");
    }
    report.checks.push({ label: "storefront-session-request-timeout", status: "passed" });
    report.checks.push({ label: "storefront-session-timeout-recovery", status: "passed" });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    report.failures.push({ label: "storefront-session-request-timeout", message });
    report.checks.push({ label: "storefront-session-request-timeout", status: "failed", message });
  } finally {
    await homeSessionTimeoutContext.close();
  }

  const productDetailAttributionContext = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 1,
    reducedMotion: "reduce",
  });
  try {
    const productDetailAttributionPage =
      await productDetailAttributionContext.newPage();
    const response = await productDetailAttributionPage.goto(
      baseUrl +
        "/duft/rabanne-1-million?src=tiktok&cmp=qa_product_detail&content=qa_product_detail_content",
      { waitUntil: "networkidle", timeout: 45_000 },
    );
    if (!response?.ok()) {
      throw new Error(
        "product detail attribution QA did not load: HTTP " +
          String(response?.status() ?? "no response"),
      );
    }

    const candidates = [
      productDetailAttributionPage.getByRole("link", { name: "Düfte" }),
      productDetailAttributionPage.getByRole("link", { name: "Duftberatung öffnen" }),
      productDetailAttributionPage.getByRole("link", { name: "Mit anderem Duft vergleichen →" }),
      productDetailAttributionPage.locator("footer").getByRole("link", { name: "Transparenz" }),
    ];

    for (const link of candidates) {
      const href = await link.first().getAttribute("href");
      if (!href) throw new Error("product detail internal link is missing its href");
      const url = new URL(href, baseUrl);
      if (
        url.searchParams.get("src") !== "tiktok" ||
        url.searchParams.get("cmp") !== "qa_product_detail" ||
        url.searchParams.get("content") !== "qa_product_detail_content"
      ) {
        throw new Error("product detail navigation lost acquisition attribution");
      }
    }

    report.checks.push({
      label: "product-detail-navigation-attribution",
      status: "passed",
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    report.failures.push({
      label: "product-detail-navigation-attribution",
      message,
    });
    report.checks.push({
      label: "product-detail-navigation-attribution",
      status: "failed",
      message,
    });
  } finally {
    await productDetailAttributionContext.close();
  }

  const comparisonContext = await browser.newContext();
  try {
    const comparisonPage = await comparisonContext.newPage();
    const response = await comparisonPage.goto(
      `${baseUrl}/vergleich?utm_source=qa&src=tiktok&cmp=qa_comparison_campaign&content=qa_comparison_content`,
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
    const comparisonProductLink = comparisonPage.locator(
      '[data-dufynd-comparison-side="left"]',
    );
    const comparisonProductHref =
      await comparisonProductLink.getAttribute("href");
    if (!comparisonProductHref) {
      throw new Error(
        "free comparison product card is missing its product-detail href",
      );
    }
    const comparisonProductUrl = new URL(
      comparisonProductHref,
      baseUrl,
    );
    if (
      comparisonProductUrl.searchParams.get("src") !== "tiktok" ||
      comparisonProductUrl.searchParams.get("cmp") !==
        "qa_comparison_campaign" ||
      comparisonProductUrl.searchParams.get("content") !==
        "qa_comparison_content"
    ) {
      throw new Error(
        "free comparison product navigation lost acquisition attribution",
      );
    }

    const comparisonCatalogHref = await comparisonPage
      .locator("header")
      .getByRole("link", { name: "Duftkatalog" })
      .getAttribute("href");
    const comparisonPairHref = await comparisonPage
      .locator(".dufynd-comparison-pair-card")
      .first()
      .getAttribute("href");
    for (const [label, href] of [
      ["comparison catalog", comparisonCatalogHref],
      ["documented comparison pair", comparisonPairHref],
    ]) {
      if (!href) {
        throw new Error(`${label} link is missing its href`);
      }
      const internalUrl = new URL(href, baseUrl);
      if (
        internalUrl.searchParams.get("src") !== "tiktok" ||
        internalUrl.searchParams.get("cmp") !==
          "qa_comparison_campaign" ||
        internalUrl.searchParams.get("content") !==
          "qa_comparison_content"
      ) {
        throw new Error(
          `${label} navigation lost acquisition attribution`,
        );
      }
    }

    const comparisonFooter = comparisonPage.locator("footer");
    for (const name of [
      "Duftkatalog",
      "Transparenz",
      "Impressum",
      "Datenschutz",
    ]) {
      const href = await comparisonFooter
        .getByRole("link", { name })
        .getAttribute("href");
      if (!href) {
        throw new Error(`comparison footer ${name} link is missing its href`);
      }
      const footerUrl = new URL(href, baseUrl);
      if (
        footerUrl.searchParams.get("src") !== "tiktok" ||
        footerUrl.searchParams.get("cmp") !== "qa_comparison_campaign" ||
        footerUrl.searchParams.get("content") !== "qa_comparison_content"
      ) {
        throw new Error(
          `comparison footer ${name} navigation lost acquisition attribution`,
        );
      }
    }

    const documentedComparisonUrl = new URL(
      comparisonPairHref,
      baseUrl,
    );
    const comparisonDetailPage = await comparisonContext.newPage();
    const comparisonDetailResponse = await comparisonDetailPage.goto(
      documentedComparisonUrl.href,
      { waitUntil: "networkidle", timeout: 45_000 },
    );
    if (!comparisonDetailResponse?.ok()) {
      throw new Error(
        "documented comparison attribution QA did not load: HTTP " +
          String(comparisonDetailResponse?.status() ?? "no response"),
      );
    }

    const detailProductHref = await comparisonDetailPage
      .locator('[data-dufynd-comparison-side="left"] a')
      .first()
      .getAttribute("href");
    const detailHeaderHref = await comparisonDetailPage
      .locator("header")
      .getByRole("link", { name: "Weitere Vergleiche" })
      .getAttribute("href");
    const detailBreadcrumbHref = await comparisonDetailPage
      .getByRole("navigation", { name: "Breadcrumb" })
      .getByRole("link", { name: "Vergleiche" })
      .getAttribute("href");
    const detailFooterHref = await comparisonDetailPage
      .locator("footer")
      .getByRole("link", { name: "Transparenz" })
      .getAttribute("href");

    for (const [label, href] of [
      ["documented comparison product", detailProductHref],
      ["documented comparison header", detailHeaderHref],
      ["documented comparison breadcrumb", detailBreadcrumbHref],
      ["documented comparison footer", detailFooterHref],
    ]) {
      if (!href) {
        throw new Error(`${label} link is missing its href`);
      }
      const detailUrl = new URL(href, baseUrl);
      if (
        detailUrl.searchParams.get("src") !== "tiktok" ||
        detailUrl.searchParams.get("cmp") !== "qa_comparison_campaign" ||
        detailUrl.searchParams.get("content") !== "qa_comparison_content"
      ) {
        throw new Error(
          `${label} navigation lost acquisition attribution`,
        );
      }
    }
    await comparisonDetailPage.close();

    report.checks.push({
      label: "comparison-detail-navigation-attribution",
      status: "passed",
    });
    report.checks.push({
      label: "comparison-footer-navigation-attribution",
      status: "passed",
    });
    report.checks.push({
      label: "comparison-internal-navigation-attribution",
      status: "passed",
    });
    report.checks.push({
      label: "comparison-product-navigation-attribution",
      status: "passed",
    });
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
    const restoredLink = backupPage.locator('.dufynd-library-card a[href*="/duft/xerjoff-naxos"]');
    if ((await restoredLink.count()) !== 1 || new URL(await restoredLink.getAttribute("href"), baseUrl).pathname !== "/duft/xerjoff-naxos") {
      throw new Error("library backup did not restore the saved fragrance");
    }
    if ((await backupPage.locator(".dufynd-library-card").count()) !== 1) {
      throw new Error("wishlist did not render the immersive library card");
    }
    if ((await backupPage.locator("[data-dufynd-library-card-stage]").count()) !== 1) {
      throw new Error("wishlist immersive library card is missing its product stage");
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
      .locator('a')
      .evaluateAll((links) =>
        Array.from(
          new Set(
            links
              .map((link) => new URL(link.href).pathname)
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

    const exposedBlockedRoutes = detailRoutes.filter((route) =>
      blockedFragranceRoutes.has(route),
    );
    if (exposedBlockedRoutes.length) {
      throw new Error(
        `source-blocked fragrances leaked into the catalog: ${exposedBlockedRoutes.join(", ")}`,
      );
    }

    for (const route of [...blockedFragranceRoutes].sort()) {
      const slug = route.replace(/^\/duft\//, "");
      const label = `blocked-detail-${slug}-390`;
      const url = `${baseUrl}${route}`;
      try {
        const response = await sweepPage.goto(url, {
          waitUntil: "domcontentloaded",
          timeout: 45_000,
        });
        if (response?.status() !== 404) {
          throw new Error(
            `source-blocked fragrance route returned HTTP ${response?.status() ?? "no response"} instead of 404`,
          );
        }
        report.checks.push({
          label,
          status: "passed",
          http_status: 404,
        });
      } catch (error) {
        const message =
          error instanceof Error ? error.message : String(error);
        report.failures.push({ label, url, message });
        report.checks.push({ label, status: "failed", message });
      }
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
