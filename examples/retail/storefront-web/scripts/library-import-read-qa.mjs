import assert from 'node:assert/strict';

export async function verifyLibraryImportReadFailure(browser, baseUrl) {
  const key = 'scentai_fragrance_library_v1';
  const saved = {version:1,owned:['SC-XERJOFF-NAXOS-100'],wishlist:['SC-RABANNE-1-MILLION-EDT-100']};
  const backup = {version:1,owned:[],wishlist:['SC-XERJOFF-NAXOS-100']};
  let cases = 0;
  for(const width of [390,1440]) {
    for(const mode of ['sammlung','merkliste']) {
      for(const failure of ['denied','invalid-json']) {
        for(const allow of [false,true]) {
          const context = await browser.newContext({viewport:{width,height:900}});
          const page = await context.newPage();
          try {
            await context.addInitScript(({key,saved})=>{
              if(!sessionStorage.getItem('qa_import_read_seeded')){
                localStorage.setItem(key,JSON.stringify(saved));sessionStorage.setItem('qa_import_read_seeded','1');
              }
            },{key,saved});
            await page.route('**/api/session',r=>r.fulfill({json:{session_id:'qa-import-read',name:'QA'}}));
            await page.route('**/api/analytics/events',r=>r.fulfill({json:{ok:true}}));
            await page.goto(`${baseUrl}/${mode}`);
            await page.getByRole('button',{name:'Sicherung importieren',exact:true}).waitFor();
            await page.evaluate(({key,failure,allow})=>{
              window.qaImportGet = Storage.prototype.getItem;
              Storage.prototype.getItem = function(k){
                if(k===key){if(failure==='invalid-json')return '{invalid';throw new DOMException('Denied','SecurityError');}
                return window.qaImportGet.call(this,k);
              };
              window.qaImportConfirmations = [];
              window.confirm = message => {window.qaImportConfirmations.push(message);return allow};
            },{key,failure,allow});
            const input=page.locator('input[type=file]');
            await input.setInputFiles({name:'dufynd-backup.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(backup))});
            await page.waitForFunction(()=>[...document.querySelectorAll('[role=status]')].some(e=>/Sicherung geladen:|Import abgebrochen\./.test(e.textContent)));
            const messages=await page.evaluate(()=>window.qaImportConfirmations);
            assert.equal(messages.length,1,`${mode}/${width}/${failure}/${allow}: unreadable current data must require replacement confirmation`);
            assert.match(messages[0],/ersetzt deine aktuelle Merkliste und Sammlung/);
            assert.deepEqual(await page.evaluate(key=>JSON.parse(window.qaImportGet.call(localStorage,key)),key),allow?backup:saved,'cancel preserves both lists; only confirmed import may replace them');
            await page.getByText(allow?'Sicherung geladen: 1 gemerkt, 0 in Sammlung.':'Import abgebrochen. Deine aktuelle Auswahl bleibt erhalten.',{exact:true}).waitFor();
            assert.equal(await input.inputValue(),'','same file remains selectable');
            await page.evaluate(()=>{Storage.prototype.getItem=window.qaImportGet});
            await page.reload();
            await page.getByRole('button',{name:'Sicherung importieren',exact:true}).waitFor();
            assert.deepEqual(await page.evaluate(key=>JSON.parse(localStorage.getItem(key)),key),allow?backup:saved,'confirmed/cancelled state persists after reload');
            cases++;
          } finally {await context.close()}
        }
      }
    }
  }
  return cases;
}
