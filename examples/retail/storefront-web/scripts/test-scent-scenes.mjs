import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import vm from 'node:vm';
import ts from 'typescript';
const require=createRequire(import.meta.url);
const source=readFileSync(new URL('../components/ScentScene.tsx',import.meta.url),'utf8');
const code=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX}}).outputText;
const context={exports:{},require};vm.runInNewContext(code,context);
const facts=JSON.parse(readFileSync(new URL('../../data/dufynd_discovery_qualification.json',import.meta.url),'utf8')).products;
const pilots=JSON.parse(readFileSync(new URL('../../data/dufynd_release_pilots.json',import.meta.url),'utf8')).pilots;
const scenes=pilots.map(p=>{const f=facts.find(f=>f.product_id===p.product_id);const scene=context.exports.sceneFor(f.name);assert.ok(scene,`Missing curated scene: ${f.name}`);return scene;});
assert.equal(new Set(scenes.map(s=>s.kind)).size,scenes.length,'Each review product has a distinct composition, not a palette-only variant');
assert.ok(!/<img|<image|https?:\/\//.test(source),'Original vector scenes have no external image asset');
const labelSource=readFileSync(new URL('../lib/noteLabels.ts',import.meta.url),'utf8');
const labelContext={exports:{}};
vm.runInNewContext(ts.transpileModule(labelSource,{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,labelContext);
for(const f of facts) for(const note of Object.values(f.notes).flat()) {
 assert.ok(labelContext.exports.NOTE_LABELS_DE[note.trim().toLocaleLowerCase('en-US')],`Missing German review note label: ${note}`);
}
console.log(`${scenes.length} explicitly mapped, distinct review compositions; no external images or bottle replica.`);
