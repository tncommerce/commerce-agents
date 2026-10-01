import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import ts from "typescript";

function compile(file, context) {
  const source = fs.readFileSync(new URL(file, import.meta.url), "utf8");
  const code = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS },
  }).outputText;
  const module = { exports: {} };
  vm.runInNewContext(code, { ...context, module, exports: module.exports });
  return module.exports;
}

function client(fetchResult) {
  const requests = [];
  const timers = new Map();
  let timerId = 0;
  const context = {
    AbortController,
    URLSearchParams,
    process: { env: { NEXT_PUBLIC_API_URL: "https://api.dufynd.test/" } },
    fetch: (url, init) => {
      requests.push({ url, init });
      return fetchResult(init, requests.length);
    },
    setTimeout: (callback, delay) => {
      const id = ++timerId;
      timers.set(id, { callback, delay });
      return id;
    },
    clearTimeout: (id) => timers.delete(id),
  };
  const shared = compile("../../../web-shared/api.ts", context);
  const api = compile("../lib/api.ts", {
    ...context,
    require: (name) => {
      assert.equal(name, "web-shared");
      return shared;
    },
  });
  api.api.session = "catalog-session";
  return { ...api, requests, timers };
}

const products = [{ product_id: "SC-TEST", title: "Existing catalog product" }];
const success = () => ({ ok: true, json: async () => ({ products }) });

{
  const env = client(success);
  const result = await env.fetchProducts();
  assert.equal(result, products);
  assert.equal(env.requests[0].url, "https://api.dufynd.test/api/products?limit=100");
  assert.equal(env.requests[0].init.headers["X-Session-Id"], "catalog-session");
  assert.equal(env.requests[0].init.signal.aborted, false);
  assert.equal(env.timers.size, 0);
}

for (const response of [
  () => ({ ok: false, json: () => { throw new Error("Do not parse failed response"); } }),
  () => Promise.reject(new Error("offline")),
  () => ({ ok: true, json: async () => { throw new SyntaxError("invalid JSON"); } }),
  () => ({ ok: true, json: async () => ({}) }),
]) {
  const env = client(response);
  assert.equal(await env.fetchProducts(), null);
  assert.equal(env.timers.size, 0);
}

{
  const env = client(() => ({ ok: true, json: async () => ({ products: [] }) }));
  assert.equal((await env.fetchProducts()).length, 0);
  assert.equal(env.timers.size, 0);
}

function untilAborted(signal) {
  return new Promise((_, reject) => {
    signal.addEventListener("abort", () => reject(new Error("aborted")), { once: true });
  });
}

for (const stall of ["headers", "body"]) {
  const env = client((init, attempt) => {
    if (attempt > 1) return success();
    if (stall === "headers") return untilAborted(init.signal);
    return { ok: true, json: () => untilAborted(init.signal) };
  });
  const stalled = env.fetchProducts();
  // Let a successful header response enter the deliberately stalled body read.
  await Promise.resolve();
  assert.equal(env.timers.size, 1);
  const timer = [...env.timers.values()][0];
  assert.equal(timer.delay, 8_000);
  assert.equal(env.requests[0].init.signal.aborted, false);
  timer.callback();
  assert.equal(await stalled, null);
  assert.equal(env.requests[0].init.signal.aborted, true);
  assert.equal(env.timers.size, 0);
  assert.equal(await env.fetchProducts(), products);
  assert.notEqual(env.requests[0].init.signal, env.requests[1].init.signal);
  assert.equal(env.requests[1].init.signal.aborted, false);
  assert.equal(env.timers.size, 0);
}

{
  const env = client((init, attempt) => attempt === 1 ? untilAborted(init.signal) : success());
  const pending = env.fetchProducts();
  assert.equal(await env.fetchProducts(), products);
  assert.equal(env.timers.size, 1);
  [...env.timers.values()][0].callback();
  assert.equal(await pending, null);
  assert.equal(env.requests[1].init.signal.aborted, false);
  assert.equal(env.timers.size, 0);
}

console.log("DUFYND catalog requests: success, failures, header/body timeout and independent recovery passed.");
