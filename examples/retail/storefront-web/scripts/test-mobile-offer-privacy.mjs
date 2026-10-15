// Compile the actual component, then exercise its effect with isolated geometry.
// This tests visibility/subscription behavior, not React hydration or layout.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const ts = require('typescript');
const input = process.argv[2] || new URL('../components/MobileOfferBar.tsx', import.meta.url);
const compiled = ts.transpileModule(fs.readFileSync(input, 'utf8'), {
  reportDiagnostics: true,
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
});
assert.deepEqual(compiled.diagnostics, []);
let cases = 0;
const check = (actual, expected, message) => { assert.equal(actual, expected, message); cases++; };
function fixture({ observer = true, triggerPresent = true, offersPresent = true, preferencesPresent = true } = {}) {
  let visible = false, effect;
  const position = { trigger: -100, offers: -100, preferences: 1000 };
  const element = key => ({ getBoundingClientRect: () => ({ top: position[key], bottom: position[key] + 50, left: 0, right: 300 }) });
  const trigger = triggerPresent ? element('trigger') : null;
  const offers = offersPresent ? element('offers') : null;
  const preferences = preferencesPresent ? element('preferences') : null;
  const events = new Map(), observed = new Set();
  let observerCallback, disconnected = false;
  const module = { exports: {} };
  const scope = {
    module, exports: module.exports,
    window: { innerHeight: 844, innerWidth: 390,
      addEventListener: (type, cb) => events.set(type, cb),
      removeEventListener: (type, cb) => { assert.equal(events.get(type), cb); events.delete(type); },
    },
    document: {
      getElementById: id => id === 'dufynd-hero-offer-cta' ? trigger : id === 'angebote' ? offers : null,
      querySelector: selector => { assert.equal(selector, '[data-measurement-choice]'); return preferences; },
    },
    require: id => {
      if (id === 'react') return { useState: () => [false, value => { visible = value; }], useEffect: callback => { effect = callback; } };
      if (id === 'react/jsx-runtime') return { jsx: () => null, jsxs: () => null };
      if (id === '@/components/OfferSectionLink') return { default: () => null };
      throw Error('Unexpected dependency ' + id);
    },
  };
  if (observer) scope.IntersectionObserver = class {
    constructor(callback) { observerCallback = callback; }
    observe(node) { observed.add(node); }
    disconnect() { disconnected = true; observed.clear(); }
  };
  vm.runInNewContext(compiled.outputText, scope, { timeout: 1000 });
  module.exports.default({ brand: 'QA', name: 'QA', productId: 'SC-QA' });
  const cleanup = effect();
  return { position, observed, preferences, events, scope,
    visible: () => visible,
    sync: () => observer ? observerCallback() : events.get('scroll')(),
    resize: () => observer ? observerCallback() : events.get('resize')(),
    cleanup: () => { cleanup?.(); return observer ? disconnected : events.size === 0; },
  };
}
for (const observer of [true, false]) {
  const f = fixture({ observer });
  check(f.visible(), true, 'Purchase shortcut remains available away from offers and privacy controls');
  f.position.preferences = 700; f.sync();
  check(f.visible(), false, 'Visible privacy controls must not be covered by the mobile purchase bar');
  f.position.preferences = 843; f.sync();
  check(f.visible(), false, 'Even a partially visible privacy region suppresses the bar');
  f.position.preferences = 1000; f.sync();
  check(f.visible(), true, 'Leaving privacy region restores the purchase shortcut');
  f.position.trigger = 20; f.sync();
  check(f.visible(), false, 'Visible hero CTA prevents a duplicate purchase entry');
  f.position.trigger = -100; f.position.offers = 700; f.sync();
  check(f.visible(), false, 'Visible merchant offers prevent duplicate purchase bar');
  f.position.offers = -100; f.sync();
  check(f.visible(), true, 'Scrolling beyond offers restores purchase bar');
  f.scope.window.innerHeight = 1200; f.resize();
  check(f.visible(), false, 'Resize can reveal the privacy region');
  if (observer) check(f.observed.has(f.preferences), true, 'Privacy geometry is part of the live observer');
  else check(f.events.size, 2, 'No-IntersectionObserver fallback handles scrolling and resizing');
  check(f.cleanup(), true, 'Observer/listeners are removed at unmount');
  for (const options of [{ preferencesPresent: false }, { offersPresent: false }]) {
    const optional = fixture({ observer, ...options });
    check(optional.visible(), true, 'Optional missing elements do not disable purchase navigation');
    check(optional.cleanup(), true, 'Optional-element lifecycle still cleans up');
  }
  const absent = fixture({ observer, triggerPresent: false });
  check(absent.visible(), false, 'No trigger fails closed');
  check(absent.events.size + absent.observed.size, 0, 'No stale subscriptions without trigger');
}
console.log(JSON.stringify({ status: 'PASS', cases, networkRequests: 0, scope: 'Actual MobileOfferBar effect with isolated geometry; full React browser suite remains separate' }));
