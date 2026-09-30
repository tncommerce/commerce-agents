import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import ts from "typescript";

function compile(file, context) {
  const source = fs.readFileSync(new URL(file, import.meta.url), "utf8");
  const code = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const module = { exports: {} };
  vm.runInNewContext(code, { ...context, module, exports: module.exports });
  return module.exports;
}

function loader({ registered = false, server = false, existing = false } = {}) {
  const scripts = [];
  const timers = new Map();
  let timerId = 0;
  let ready = registered;
  function script() {
    const element = new EventTarget();
    element.dataset = {};
    element.remove = () => scripts.splice(scripts.indexOf(element), 1);
    return element;
  }
  if (existing) scripts.push(script());
  const context = {
    customElements: { get: () => ready ? class {} : undefined },
    document: {
      querySelector: () => scripts[0] || null,
      createElement: script,
      head: { appendChild: (element) => scripts.push(element) },
    },
    setTimeout: (callback) => { timers.set(++timerId, callback); return timerId; },
    clearTimeout: (id) => timers.delete(id),
  };
  if (!server) context.window = {};
  const { ensureModelViewer } = compile("../lib/modelViewerLoader.ts", context);
  return { ensureModelViewer, scripts, timers, register: () => { ready = true; } };
}

for (const config of [{ registered: true }, { server: true }]) {
  const env = loader(config);
  await env.ensureModelViewer();
  assert.equal(env.scripts.length, 0);
}

for (const existing of [false, true]) {
  const env = loader({ existing });
  const first = env.ensureModelViewer();
  const second = env.ensureModelViewer();
  assert.equal(first, second);
  assert.equal(env.scripts.length, 1);
  env.register();
  env.scripts[0].dispatchEvent(new Event("load"));
  await Promise.all([first, second]);
  assert.equal(env.timers.size, 0);
  await env.ensureModelViewer();
  assert.equal(env.scripts.length, 1);
}

for (const failure of ["error", "unregistered-load", "timeout"]) {
  const env = loader();
  const first = env.ensureModelViewer();
  const second = env.ensureModelViewer();
  const firstRejected = assert.rejects(first, /3D viewer failed/);
  const secondRejected = assert.rejects(second, /3D viewer failed/);
  if (failure === "timeout") [...env.timers.values()][0]();
  else env.scripts[0].dispatchEvent(new Event(failure === "error" ? "error" : "load"));
  await Promise.all([firstRejected, secondRejected]);
  assert.equal(env.scripts.length, 0);
  assert.equal(env.timers.size, 0);
  const retry = env.ensureModelViewer();
  assert.notEqual(retry, first);
  assert.equal(env.scripts.length, 1);
  env.register();
  env.scripts[0].dispatchEvent(new Event("load"));
  await retry;
}

// Exercise the actual component's load/error callbacks with deterministic hooks.
const state = [true, null, null, false];
let cursor = 0;
const element = (type, props) => ({ type, props });
const FragranceVisual = () => {};
const component = compile("../components/FragranceModel3D.tsx", {
  require: (name) => {
    if (name === "react/jsx-runtime") return { jsx: element, jsxs: element };
    if (name === "react") return {
      createElement: element,
      useEffect: () => {},
      useState: () => { const index = cursor++; return [state[index], (value) => { state[index] = value; }]; },
    };
    if (name === "./FragranceVisual") return { default: FragranceVisual };
    if (name === "@/lib/modelViewerLoader") return { ensureModelViewer: async () => {} };
    throw new Error(`Unexpected import: ${name}`);
  },
  URL,
}).default;
const props = { modelUrl: "/products/test.glb", imageUrl: "/test.webp", cutoutUrl: "/cutout.webp", alt: "Exact product", priority: true };
function render(input = props) { cursor = 0; return component(input); }
let tree = render();
assert.equal(tree.props.children[2], null);
tree.props.children[1].props.onload();
tree = render();
assert.equal(tree.props.children[2].props.children, "Ziehen zum Drehen");
tree.props.children[1].props.onerror();
tree = render();
assert.equal(tree.type, FragranceVisual);
assert.equal(tree.props.imageUrl, props.imageUrl);
assert.equal(tree.props.cutoutUrl, props.cutoutUrl);
assert.equal(tree.props.alt, props.alt);
assert.equal(tree.props.priority, true);
assert.equal(render({ ...props, modelUrl: "/products/other.glb" }).props.children[1].type, "model-viewer");
assert.equal(render({ ...props, modelUrl: "//external.invalid/test.glb" }).type, FragranceVisual);
console.log("DUFYND 3D recovery: shared loads, retry, timeout and image fallback verified.");
