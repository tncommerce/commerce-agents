// Test-only VM adapter. The real consent, acquisition and analytics modules share
// one window/context. Unknown is the default; positive tests must opt in explicitly.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { webcrypto } from 'node:crypto';
import vm from 'node:vm';
import ts from 'typescript';

const compiled = new Map();
function compile(file) {
  const key = String(file);
  if (!compiled.has(key)) {
    const result = ts.transpileModule(readFileSync(file, 'utf8'), {
      fileName: key, reportDiagnostics: true,
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
    });
    assert.deepEqual(result.diagnostics, [], `TypeScript syntax: ${key}`);
    compiled.set(key, result.outputText);
  }
  return compiled.get(key);
}
export function deferred() {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return { promise, resolve };
}
export async function drain() { for (let i = 0; i < 16; i++) await Promise.resolve(); }

export function measurementClient({
  initialize = async () => 'qa-functional-transport-123456',
  post = async () => ({ ok: true }),
  browserWindow, referrer = '', choice = 'unknown', ssr = false,
  origin = 'https://dufynd.test', search = '',
  apiBase = 'https://api.dufynd.test/api', apiSession = null,
  blockedStorage = false, blockedPreference = false,
  analyticsFile = new URL('../lib/analytics.ts', import.meta.url),
} = {}) {
  const requests = [], timers = new Map(), local = new Map(), session = new Map();
  const windowEvents = new Map(), documentEvents = new Map();
  const touched = { preferenceReads: 0, preferenceWrites: 0, reads: 0, writes: 0, removals: 0, network: 0 };
  let initializations = 0, timerId = 0;
  const storage = (map, blocked, preference) => ({
    getItem(key) {
      touched[preference ? 'preferenceReads' : 'reads']++;
      if (blocked) throw Error('storage blocked by fixture');
      return map.get(key) ?? null;
    },
    setItem(key, value) {
      touched[preference ? 'preferenceWrites' : 'writes']++;
      if (blocked) throw Error('storage blocked by fixture');
      map.set(key, String(value));
    },
    removeItem(key) {
      touched.removals++;
      if (blocked) throw Error('storage blocked by fixture');
      map.delete(key);
    },
  });
  const add = (events, type, listener) => events.set(type, [...(events.get(type) || []), listener]);
  const location = { origin, search, href: `${origin}/${search}`, ...browserWindow?.location };
  const window = {
    ...browserWindow, location,
    localStorage: browserWindow?.localStorage ?? storage(local, blockedPreference, true),
    sessionStorage: browserWindow?.sessionStorage ?? storage(session, blockedStorage, false),
    addEventListener: (type, listener) => add(windowEvents, type, listener),
    history: { state: {}, replaceState(_state, _title, href) {
      const next = new URL(href, location.origin);
      location.href = next.href; location.search = next.search;
    } },
  };
  const document = {
    referrer, visibilityState: 'visible', querySelectorAll: () => [],
    addEventListener: (type, listener) => add(documentEvents, type, listener),
  };
  const api = { session: apiSession, base: apiBase, headers: () => ({ 'X-Session-Id': api.session }) };
  const context = vm.createContext({
    URL, URLSearchParams, AbortController, crypto: webcrypto, Element: class {},
    ...(!ssr ? { window, document } : {}),
    fetch(url, init) {
      const parsed = new URL(url), root = new URL(api.base);
      assert.equal(parsed.origin, root.origin);
      assert.equal(parsed.pathname, `${root.pathname.replace(/\/$/, '')}/analytics/events`);
      assert.equal(parsed.searchParams.get('measurement'), 'granted-v1', 'Telemetry needs an explicit consent declaration');
      touched.network++;
      requests.push({ url, init, payload: JSON.parse(init.body) });
      return post(requests.length, init);
    },
    setTimeout(callback, delay) { timers.set(++timerId, { callback, delay }); return timerId; },
    clearTimeout: id => timers.delete(id),
  });
  const cache = new Map();
  function load(name) {
    if (name === './api') return { api, initializeAnalyticsSession: () => initialize(++initializations) };
    assert.ok(['./measurementConsent', './acquisitionEntry', './analytics'].includes(name), `Unexpected module ${name}`);
    if (cache.has(name)) return cache.get(name).exports;
    const file = name === './analytics' ? analyticsFile : new URL(`../lib/${name.slice(2)}.ts`, import.meta.url);
    const module = { exports: {} }; cache.set(name, module);
    const execute = vm.runInContext(`(function(require,module,exports){${compile(file)}\n})`, context, { timeout: 1000 });
    execute(load, module, module.exports);
    return module.exports;
  }
  const consent = load('./measurementConsent');
  if (choice !== 'unknown') consent.setMeasurementChoice(choice);
  const analytics = load('./analytics');
  return {
    api, consent, ...analytics, requests, timers, touched, session, local, window, document,
    get initializations() { return initializations; },
    dispatch(type, event = {}) { for (const fn of windowEvents.get(type) || []) fn(event); },
  };
}
