import assert from 'node:assert/strict';
import {writeFileSync} from 'node:fs';

const waveIds = [
  'SC-BURBERRY-GODDESS-EDP-100', 'SC-PRADA-PARADOXE-EDP-90',
  'SC-CAROLINA-HERRERA-GOOD-GIRL-EDP-80', 'SC-CHANEL-COCO-MADEMOISELLE-EDP-100',
  'SC-GUERLAIN-MON-GUERLAIN-EDP-100',
];

/** Local private routes only. Any attempted API/analytics/merchant call fails this QA. */
export async function qualifiedReviewQa(browser, {base, out, pilots, facts}) {
  const report = [];
  const wave = waveIds.map(id => {
    const pilot = pilots.find(p => p.product_id === id);
    const fact = facts.find(f => f.product_id === id);
    assert.ok(pilot && fact, `Qualified review profile missing: ${id}`);
    assert.equal(fact.image_rights_status, 'HOLD');
    assert.equal(fact.publication_authorized, false);
    return {...pilot, fact};
  });
  for (const width of [320,390,768,1440]) {
   for (const p of wave) {
    console.log(`Checking private review ${p.product_id} at ${width}px`);
    const context = await browser.newContext({viewport:{width,height:900},reducedMotion:'reduce'});
    // Deliberately grant the optional setting in this isolated browser: even then
    // this private explorer must never call measurement or merchant APIs.
    await context.addInitScript(() => localStorage.setItem('dufynd_measurement_preference_v1', JSON.stringify({version:1,choice:'granted',savedAt:Date.now()})));
    const forbidden = [], errors = [];
    await context.route('**/*', route => {
      const url = new URL(route.request().url());
      if (url.origin !== new URL(base).origin || /\/(api|analytics|clickout)(\/|$)/.test(url.pathname)) {
        forbidden.push(url.origin + url.pathname);
        return route.abort();
      }
      return route.continue();
    });
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
      await page.goto(`${base}/review/duft/${p.slug}`);
      await page.locator('[data-private-review-explorer][data-review-ready=true]').waitFor();
      const main = page.locator('[data-review-product]');
      assert.equal(await main.getAttribute('data-review-product'), p.product_id);
      const identity = main.locator('h1').locator('..');
      assert.ok((await identity.innerText()).includes(`${p.fact.volume_ml} ml`));
      assert.ok((await identity.innerText()).includes(p.fact.concentration));
      assert.equal(await page.locator('img').count(),0,'Honest fallback, no unlicensed picture');
      assert.equal(await page.locator('[data-dufynd-studio-source-hold]').count(),1);
      if ([390,1440].includes(width)) await page.screenshot({path:`${out}/verified-${p.slug}-${width}-profile.png`});
      await page.locator('#quellen summary').click();
      const sources = page.locator('#quellen');
      assert.ok((await sources.innerText()).includes(p.fact.checked_at));
      assert.ok((await sources.innerText()).includes('IMAGE_HOLD'));
      assert.equal(await sources.locator(`a[href="${p.fact.notes_source.url}"]`).count() >= 1,true);
      await page.locator('header').getByRole('link',{name:'Zur privaten Auswahl'}).click();
      const explorer = page.locator('[data-private-review-explorer]');
      const search = explorer.getByRole('searchbox',{name:'Review-Düfte suchen'});
      const brand = explorer.getByRole('combobox',{name:'Marke',exact:true});
      await search.fill(p.fact.name);
      await brand.selectOption({label:p.fact.brand === 'CHANEL' ? 'Chanel' : p.fact.brand});
      const card = explorer.locator(`[data-review-card="${p.product_id}"]`);
      await card.waitFor();
      assert.equal(await explorer.locator('[data-review-card]').count(),1,'Exact search and brand select only the intended variant');
      const pick = card.getByRole('button');
      await pick.focus();
      await page.keyboard.press('Shift+Tab');
      await page.keyboard.press('Tab');
      assert.equal(await pick.evaluate(el => document.activeElement === el),true,'Keyboard returns to the selection button');
      assert.ok(await pick.evaluate(el => getComputedStyle(el).outlineStyle !== 'none'),'Visible keyboard focus');
      const bounds = await pick.boundingBox();
      assert.ok(bounds.width >= 44 && bounds.height >= 44,'Touch target');
      await page.keyboard.press('Space');
      assert.equal(await pick.getAttribute('aria-pressed'),'true');
      if ([390,1440].includes(width) && p === wave[0]) await explorer.screenshot({path:`${out}/verified-search-${width}.png`});
      // The selected first profile survives a filter which hides it.
      const other = p === wave[0] ? wave[4] : wave[0];
      await brand.selectOption('');await search.fill(other.fact.name);
      await explorer.locator(`[data-review-card="${other.product_id}"]`).getByRole('button').click();
      await search.fill('');
      const third = explorer.locator('[data-review-card]').filter({has:page.locator('button[aria-pressed=false]')}).first();
      assert.equal(await third.getByRole('button').isDisabled(),true,'Exactly two, never silently replace a selected variant');
      await search.fill(other.fact.name);
      await explorer.getByRole('button',{name:'Zwei Düfte vergleichen',exact:true}).click();
      const comparison = page.locator('[data-private-review-comparison]');
      await comparison.waitFor();
      const actualIds = await comparison.locator('[data-review-comparison-product]').evaluateAll(rows => rows.map(row => row.dataset.reviewComparisonProduct));
      assert.deepEqual(actualIds,[p.product_id,other.product_id]);
      assert.equal(await comparison.locator('[data-dufynd-comparison-evidence]').count(),1);
      const text = await comparison.innerText();
      assert.ok(text.includes('Nicht genannte Noten sind nicht sicher ausgeschlossen.'));
      assert.ok(text.includes('Keine gemeinsame Akkordangabe dokumentiert.'));
      if (p === wave[0]) {
        assert.ok((await comparison.getByRole('list',{name:'Dokumentierte gemeinsame Duftnoten',exact:true}).innerText()).includes('Lavendel'));
        if ([390,1440].includes(width)) await comparison.screenshot({path:`${out}/verified-comparison-${width}.png`});
      }
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),'No horizontal overflow');
      // Browser Back restores the same search and both selections.
      await page.goBack();await page.locator('[data-private-review-explorer][data-review-ready=true]').waitFor();await search.waitFor();
      assert.equal(await search.inputValue(),other.fact.name);
      assert.equal(await explorer.getByRole('status').innerText(),'2 von 2 Düften ausgewählt');
      // Product navigation and return preserve exact selection; no public collection writes.
      await explorer.locator(`[data-review-card="${other.product_id}"] h3 a`).click();
      await page.waitForURL(url => url.pathname.endsWith(other.slug));
      await page.goBack();await page.locator('[data-private-review-explorer][data-review-ready=true]').waitFor();await search.waitFor();
      assert.equal(await search.inputValue(),other.fact.name);
      await page.waitForFunction(() => document.querySelector('[role="status"]')?.textContent === '2 von 2 Düften ausgewählt');
      await search.fill('kein-dokumentierter-duft-xyz');
      assert.equal(await explorer.locator('[data-review-card]').count(),0);
      assert.ok((await explorer.innerText()).includes('Keine belegte Variante'));
      await explorer.getByRole('button',{name:'Suche & Filter zurücksetzen'}).click();
      assert.equal(await search.inputValue(),'');
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      report.push({product_id:p.product_id,width,passed:true,image:'IMAGE_HOLD',checks:['exact_variant','source_date','honest_fallback','search_and_brand','keyboard_focus','touch_target','exact_pair','documented_comparison','back_restores_selection','empty_search','no_overflow','no_api_or_tracking']});
    assert.deepEqual(forbidden,[],'Private review must make zero external/API/analytics requests');
    assert.deepEqual(errors,[]);
    await context.close();
   }
  }
  writeFileSync(`${out}/verified-catalog-wave.json`,JSON.stringify({public_activations:0,profiles:5,checks:report},null,2)+'\n');
  console.log(`Verified catalog wave: ${report.length} profile/width flows passed, zero tracking or merchant calls.`);
}
