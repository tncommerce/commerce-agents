import { strict as assert } from "node:assert";
import { chromium } from "playwright";
import { chooseMeasurement } from "./measurement-choice-qa.mjs";

const root = "http://127.0.0.1:3000";
const browser = await chromium.launch({headless: true});
const errors = [];
const observations = [];

async function inspectedContext(viewport) {
  const context = await browser.newContext({
    viewport,
    reducedMotion: "reduce",
    serviceWorkers: "block",
  });
  // No merchant-domain requests and no real affiliate clickout or analytics.
  await context.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.hostname === "127.0.0.1" && url.port === "3000") {
      return route.continue();
    }
    return route.abort("blockedbyclient");
  });
  return context;
}

async function catalogShare() {
  const ctx = await inspectedContext({width: 390, height: 844});
  const page = await ctx.newPage();
  page.on("pageerror", (err) => errors.push(err.message.slice(0, 220)));
  try {
    const response = await page.goto(
      root + "/duft?utm_source=qa&profil=freshness",
      {waitUntil: "networkidle"},
    );
    assert.ok(response?.ok(), "catalog first-party load failed");
    await chooseMeasurement(page, "denied");
    const search = page.getByRole("searchbox", {name: "Duft, Marke oder Profil"});
    const button = page.locator('button[aria-controls="catalog-filter-panel"]');
    await search.fill("Naxos");
    if (await button.getAttribute("aria-expanded") === "false") await button.click();
    await page.getByRole("button", {name: "Herren", exact: true}).click();
    await page.getByRole("combobox", {name: "Marke"}).selectOption("Xerjoff");
    await page.getByRole("combobox", {name: "Sortierung"}).selectOption("brand");

    const snapshot = async (label) => {
      await page.waitForTimeout(260);
      const url = new URL(page.url());
      const result = {
        label,
        path: url.pathname,
        q: url.searchParams.get("q"),
        profil: url.searchParams.get("profil"),
        zielgruppe: url.searchParams.get("zielgruppe"),
        marke: url.searchParams.get("marke"),
        sort: url.searchParams.get("sort"),
        utm_source: url.searchParams.get("utm_source"),
        search_value: await search.inputValue(),
        brand_value: await page.getByRole("combobox", {name: "Marke"}).inputValue(),
        sort_value: await page.getByRole("combobox", {name: "Sortierung"}).inputValue(),
      };
      observations.push(result);
      return result;
    };
    let actual = await snapshot("after-filter-change");
    for (const [key,value] of Object.entries({
      q:"Naxos", profil:"freshness", zielgruppe:"men",
      marke:"Xerjoff", sort:"brand", utm_source:null,
    })) {
      assert.equal(actual[key], value, "share-URL does not match control " + key);
    }
    await page.reload({waitUntil:"networkidle"});
    await chooseMeasurement(page, "denied");
    if (await button.getAttribute("aria-expanded") === "false") await button.click();
    actual = await snapshot("after-reload");
    assert.equal(actual.search_value,"Naxos");
    assert.equal(actual.brand_value,"Xerjoff");
    assert.equal(actual.sort_value,"brand");
    assert.equal(await page.getByRole("button", {name:"Herren",exact:true}).getAttribute("aria-pressed"),"true");
  } finally {
    await ctx.close();
  }
}

async function productStage(slug, width) {
  const ctx = await inspectedContext({width, height: 844});
  const page = await ctx.newPage();
  page.on("pageerror",(e)=>errors.push(e.message.slice(0,220)));
  try {
    const res = await page.goto(root + "/duft/" + slug,{waitUntil:"domcontentloaded"});
    assert.ok(res?.ok(),"product route failed");
    const state = await page.evaluate(() => {
      const hero = document.querySelector(".dufynd-fragrance-hero");
      const stage = hero?.querySelector(".dufynd-fragrance-stage-shell");
      const title = hero?.querySelector("h1");
      const offers = document.querySelector("#angebote");
      const rect = el => el ? el.getBoundingClientRect() : null;
      const a=rect(stage),b=rect(title),c=rect(offers);
      return {
        product_id:hero?.getAttribute("data-product-id")||null,
        original_status:hero?.getAttribute("data-dufynd-photo-status")||null,
        title_top:b?.top??null,
        stage_height:a?.height??null,
        stage_width:a?.width??null,
        offer_exists:!!offers,
        horizontal_overflow:document.documentElement.scrollWidth>window.innerWidth+2,
        stage_after_title:a&&b?a.top>b.top:null,
        offers_after_title:c&&b?c.top>b.top:null,
      };
    });
    observations.push({label:"product-"+slug+"-"+width, ...state});
    assert.ok(state.product_id,"no product identity");
    assert.ok(state.stage_height>0,"missing product visual stage");
    assert.equal(state.horizontal_overflow,false,"mobile content overflow");
    assert.ok(state.offer_exists,"missing offer section");
  } finally {
    await ctx.close();
  }
}

try {
  await catalogShare();
  for (const slug of ["rabanne-1-million","essential-parfums-bois-imperial","giorgio-armani-stronger-with-you-intensely"]) {
    for (const width of [320,390]) await productStage(slug,width);
  }
} catch (error) {
  console.error("BUYER_ISOLATED_DIAGNOSTICS",JSON.stringify({observations,errors}));
  console.error("BUYER_ISOLATED_FAILURE",error.message);
  process.exitCode = 1;
} finally {
  await browser.close();
}
if (!process.exitCode) {
  console.log("BUYER_ISOLATED_DIAGNOSTICS",JSON.stringify({observations,errors}));
  console.log("BUYER_ISOLATED_PASS");
}
