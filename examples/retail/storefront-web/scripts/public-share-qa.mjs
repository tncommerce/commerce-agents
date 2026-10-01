import assert from "node:assert/strict";

export async function verifyPublicShareLinks(browser, baseUrl) {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  await page.addInitScript(() => {
    window.sharedLinks = [];
    Object.defineProperty(navigator, "share", { value: undefined, configurable: true });
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText: async (url) => { window.sharedLinks.push(url); } },
      configurable: true,
    });
  });
  const query = "src=tiktok&cmp=share_qa&content=video_01&sid=private_session&sid=another_session";
  const assertPublicLink = (value, pathname, hash) => {
    const url = new URL(value);
    assert.equal(url.pathname, pathname);
    assert.equal(url.searchParams.has("sid"), false, "public links must not include a visitor session");
    assert.equal(url.searchParams.get("src"), "tiktok");
    assert.equal(url.searchParams.get("cmp"), "share_qa");
    assert.equal(url.searchParams.get("content"), "video_01");
    assert.equal(url.hash, hash);
    return url;
  };
  try {
    await page.goto(`${baseUrl}/duft/xerjoff-naxos?${query}#angebote`);
    const share = page.getByRole("button", { name: /teilen$/ });
    await share.click();
    await page.waitForFunction(() => window.sharedLinks.length === 1);
    assertPublicLink(await page.evaluate(() => window.sharedLinks[0]), "/duft/xerjoff-naxos", "#angebote");

    await page.evaluate(() => Object.defineProperty(navigator, "share", {
      value: async (payload) => { window.sharedLinks.push(payload.url); }, configurable: true,
    }));
    await share.click();
    await page.waitForFunction(() => window.sharedLinks.length === 2);
    assertPublicLink(await page.evaluate(() => window.sharedLinks[1]), "/duft/xerjoff-naxos", "#angebote");

    await page.evaluate(() => Object.defineProperty(navigator, "share", {
      value: async () => { throw new Error("share unavailable"); }, configurable: true,
    }));
    await share.click();
    await page.waitForFunction(() => window.sharedLinks.length === 3);
    assertPublicLink(await page.evaluate(() => window.sharedLinks[2]), "/duft/xerjoff-naxos", "#angebote");
    assert.equal(new URL(page.url()).searchParams.has("sid"), true,
      "sharing must not mutate the active page's navigation/session state");

    await page.goto(`${baseUrl}/duft?${query}&q=Naxos&zielgruppe=unisex#katalog`);
    await page.getByRole("button", { name: "Filterlink kopieren", exact: true }).click();
    await page.waitForFunction(() => window.sharedLinks.length === 1);
    const catalog = assertPublicLink(await page.evaluate(() => window.sharedLinks[0]), "/duft", "#katalog");
    assert.equal(catalog.searchParams.get("q"), "Naxos");
    assert.equal(catalog.searchParams.get("zielgruppe"), "unisex");
    assert.equal(new URL(page.url()).searchParams.has("sid"), true);
  } finally {
    await context.close();
  }
}
