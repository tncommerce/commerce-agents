import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';
const module = {exports:{}};
const code = ts.transpileModule(fs.readFileSync(new URL('../lib/fragranceSearchIdentity.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
vm.runInNewContext(code,{module,exports:module.exports});
const {fragranceSearchIdentity:identity,matchesRequestedVariant:variant,normalizeFragranceSearch:normalize}=module.exports;
const libre={brand:'Yves Saint Laurent',name:'Libre',concentration:'Eau de Parfum',volume_ml:90};
const matches=(f,q)=>variant(f,q)&&normalize(q).split(' ').every(t=>identity(f).includes(t));
for(const q of ['YSL Libre','Libre YSL EDP 90ml','Libre 90 ml','Yves Saint Laurent Libre']) assert.equal(matches(libre,q),true,q);
for(const q of ['YSL Libre EDT','YSL Libre 50ml','YSL Libre 190 ml']) assert.equal(matches(libre,q),false,q);
assert.equal(matches({...libre,volume_ml:150},'Libre 50 ml'),false);
assert.equal(matches({...libre,brand:'Parfums de Marly',name:'Delina',volume_ml:75},'PDM Delina EDP 75 ml'),true);
const oneMillion={brand:'Rabanne',name:'1 Million',concentration:'Eau de Toilette',volume_ml:100};
for(const q of ['1 Million EDT 100ml','Paco Rabanne 1 Million EDT 100ml','One Million','onemillion','1million','Paco Rabanne One Million EDT 100ml','ONE-MILLION EDT 100 ml']) {
  assert.equal(matches(oneMillion,q),true,q);
}
for(const q of ['One Million EDP','onemillion 50ml','1million 150 ml','One Million Lucky','One Million Elixir']) {
  assert.equal(matches(oneMillion,q),false,q);
}
const catalog=[
  {id:'rc1',...oneMillion},
  {id:'lucky',...oneMillion,name:'1 Million Lucky'},
  {id:'elixir',...oneMillion,name:'1 Million Elixir',concentration:'Extrait de Parfum'},
  {id:'50ml',...oneMillion,volume_ml:50},
  {id:'edp',...oneMillion,concentration:'Eau de Parfum'},
  {id:'other-brand',...oneMillion,brand:'Other'},
];
for(const q of ['One Million EDT 100ml','Paco Rabanne onemillion EDT 100 ml','1million EDT 100ml']) {
  assert.deepEqual(catalog.filter(f=>matches(f,q)).map(f=>f.id),['rc1'],q);
}
for(const id of ['lucky','elixir','other-brand']) {
  const product=catalog.find(f=>f.id===id);
  for(const q of ['One Million','onemillion','1million']) assert.equal(matches(product,q),false,`${id}: ${q}`);
}
assert.deepEqual(catalog.filter(f=>matches(f,'One Million EDT 50ml')).map(f=>f.id),['50ml']);
assert.deepEqual(catalog.filter(f=>matches(f,'One Million EDP 100ml')).map(f=>f.id),['edp']);
assert.equal(matches({...libre,brand:'Other'},'YSL Libre'),false);
console.log('Fragrance search: brand/product aliases, word order and exact size/concentration passed.');
