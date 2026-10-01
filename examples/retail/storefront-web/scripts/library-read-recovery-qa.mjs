import assert from 'node:assert/strict';

export async function verifyLibraryReadRecovery(browser, baseUrl) {
  const key = 'scentai_fragrance_library_v1';
  const target = 'SC-XERJOFF-NAXOS-100';
  const other = 'SC-RABANNE-1-MILLION-EDT-100';
  let cases = 0;
  for (const width of [390, 1440]) {
    for (const failure of ['denied', 'invalid-json']) {
      for (const action of ['wishlist-add', 'wishlist-remove', 'owned-add', 'owned-remove']) {
        const initial = { version: 1, owned: action === 'owned-remove' ? [target, other] : [other], wishlist: action === 'wishlist-remove' || action === 'owned-add' ? [target] : [] };
        const context = await browser.newContext({ viewport: { width, height: 900 } });
        const page = await context.newPage();
        const events = [];
        try {
          await context.addInitScript(({key,initial}) => {
            if (!sessionStorage.getItem('qa_read_seeded')) {
              localStorage.setItem(key, JSON.stringify(initial));
              sessionStorage.setItem('qa_read_seeded','1');
            }
          }, {key,initial});
          await page.route('**/api/session', r => r.fulfill({json:{session_id:'qa-library-read',name:'QA'}}));
          await page.route('**/api/analytics/events', r => {events.push(r.request().postDataJSON());return r.fulfill({json:{ok:true}})});
          await page.goto(`${baseUrl}/duft/xerjoff-naxos`);
          const wishlist = page.getByRole('button',{name:/Merken|Gemerkt|Bereits in Sammlung/});
          const owned = page.getByRole('button',{name:/Meine Sammlung|In meiner Sammlung/});
          const control = action.startsWith('wishlist') ? wishlist : owned;
          const wasPressed = action.endsWith('remove');
          await control.waitFor();
          await page.waitForFunction(({action}) => {
            const buttons = [...document.querySelectorAll('button')];
            const target = buttons.find(b => action.startsWith('wishlist') ? /Merken|Gemerkt/.test(b.textContent) : /Meine Sammlung|In meiner Sammlung/.test(b.textContent));
            return target?.getAttribute('aria-pressed') === String(action.endsWith('remove'));
          }, {action});
          await page.evaluate(({key,failure}) => {
            window.qaReadGet = Storage.prototype.getItem;
            window.qaReadSet = Storage.prototype.setItem;
            window.qaLibraryWrites = 0;
            Storage.prototype.getItem = function(k) {
              if (k === key) {
                if (failure === 'invalid-json') return '{invalid';
                throw new DOMException('Denied','SecurityError');
              }
              return window.qaReadGet.call(this,k);
            };
            Storage.prototype.setItem = function(k,v) {
              if(k === key) window.qaLibraryWrites++;
              return window.qaReadSet.call(this,k,v);
            };
          }, {key,failure});
          await control.click();
          await page.getByRole('status').filter({hasText:'Änderung konnte nicht gespeichert werden.'}).waitFor();
          assert.equal(await control.getAttribute('aria-pressed'), String(wasPressed), `${action}: failed read must preserve visible state`);
          assert.equal(await page.evaluate(()=>window.qaLibraryWrites),0,'failed read must not write');
          assert.deepEqual(await page.evaluate(key=>JSON.parse(window.qaReadGet.call(localStorage,key)),key),initial,'both saved lists must survive');
          assert.equal(events.filter(e=>/^(wishlist|collection)_(add|remove)$/.test(e.event)).length,0,'no successful save event for failed read');
          await page.evaluate(()=>{Storage.prototype.getItem=window.qaReadGet;Storage.prototype.setItem=window.qaReadSet});
          await control.click();
          await page.waitForFunction(({action}) => {
            const buttons = [...document.querySelectorAll('button')];
            const target = buttons.find(b => action.startsWith('wishlist') ? /Merken|Gemerkt/.test(b.textContent) : /Meine Sammlung|In meiner Sammlung/.test(b.textContent));
            return target?.getAttribute('aria-pressed') === String(!action.endsWith('remove'));
          }, {action});
          const expected = action === 'wishlist-add' ? {version:1,owned:[other],wishlist:[target]} : action === 'wishlist-remove' || action === 'owned-remove' ? {version:1,owned:[other],wishlist:[]} : {version:1,owned:[other,target],wishlist:[]};
          assert.deepEqual(await page.evaluate(key=>JSON.parse(localStorage.getItem(key)),key),expected,'retry changes only the intended list');
          for(let n=0;n<100&&events.filter(e=>/^(wishlist|collection)_(add|remove)$/.test(e.event)).length<1;n++)await page.waitForTimeout(50);
          assert.equal(events.filter(e=>/^(wishlist|collection)_(add|remove)$/.test(e.event)).length,1);
          await page.reload();
          await control.waitFor();
          assert.deepEqual(await page.evaluate(key=>JSON.parse(localStorage.getItem(key)),key),expected,'retry persists after reload');
          cases++;
        } finally {await context.close()}
      }
    }
  }
  return cases;
}
