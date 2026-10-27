import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';
const module = {exports:{}};
const code = ts.transpileModule(fs.readFileSync(new URL('../lib/fragranceSearchIdentity.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
vm.runInNewContext(code,{module,exports:module.exports});
const {fragranceSearchIdentity:identity,fragranceSearchTokens:tokens,matchesRequestedVariant:variant,normalizeFragranceSearch:normalize}=module.exports;
const libre={brand:'Yves Saint Laurent',name:'Libre',concentration:'Eau de Parfum',volume_ml:90};
const matches=(f,q)=>variant(f,q)&&tokens(f,q).every(t=>identity(f).includes(t));
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

// Exercise the actual public input, not invented positive product identities.
const publicSource=JSON.parse(fs.readFileSync(new URL('../lib/generated/public-fragrances.json',import.meta.url),'utf8')).products;
const catalogRows=JSON.parse(fs.readFileSync(new URL('../lib/generated/public-catalog.json',import.meta.url),'utf8')).products;
const publicIds=new Set(catalogRows.filter(p=>p.product_id.startsWith('SC-')&&p.category==='fragrance'&&p.in_stock!==false).map(p=>p.product_id));
const publicProducts=publicSource.filter(p=>publicIds.has(p.product_id)&&!p.validation?.blockers?.some(b=>String(b||'').trim()));
const required=[
  ['SC-YSL-BLACK-OPIUM-EDP-90','BlackOpium EDP 90 ml'],
  ['SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100','BoisImperial EDP 100 ml'],
  ['SC-LANCOME-LA-VIE-EST-BELLE-EDP-100','LaVieEstBelle EDP 100 ml'],
];
for(const [id,query] of required) {
  const product=publicProducts.find(p=>p.product_id===id);
  assert.ok(product,`${id} must already be public`);
  for(const q of [query,query.toUpperCase(),`${product.name} EDP ${product.volume_ml} ml`,query.replace(/EDP/,'Eau de Parfum')]) {
    assert.deepEqual(publicProducts.filter(p=>matches(p,q)).map(p=>p.product_id),[id],q);
  }
  for(const q of [query.replace(/\d+ ml/,'50 ml'),query.replace('EDP','EDT'),query.replace('EDP','extrait'),
    `${query} Intense`,`${query} Elixir`,`${query} Le Parfum`,`${query} Refill`,`${query} Nachfüllung`,
    `${query} Extreme`,`${query} Lucky`,`${query} Absolu`,query.replace(' EDP','Intense EDP'),
    query.replace(' EDP','Elixir EDP'),query.replace(' EDP','LeParfum EDP'),
    query.replace(' EDP','Refill EDP'),query.replaceAll(' ',''),query.replace('EDP ','EDP'),
    query.replace(/\d+ ml/,'50ml 90ml 100ml')]) {
    assert.deepEqual(publicProducts.filter(p=>matches(p,q)).map(p=>p.product_id),[],q);
  }
  // Synthetic negative variants never become public; a compact base name must
  // not become a prefix alias for another flanker or another bottle size.
  for(const suffix of ['Intense','Elixir','Le Parfum','Extreme','Lucky','Refill']) {
    assert.equal(matches({...product,name:`${product.name} ${suffix}`},query),false,`${query}: ${suffix}`);
  }
  for(const volume_ml of [50,150]) assert.equal(matches({...product,volume_ml},query),false);
}
for(const q of ['YSL BLACKOPIUM EDP 90ml','Yves-Saint-Laurent BlackOpium EDP 90 ml']) {
  assert.deepEqual(publicProducts.filter(p=>matches(p,q)).map(p=>p.product_id),['SC-YSL-BLACK-OPIUM-EDP-90'],q);
}
assert.equal(matches(publicProducts.find(p=>p.name==='Bois Impérial'),'BOISIMPÉRIAL EDP 100 ml'),true);
const completeNames=new Map();
for(const product of publicProducts) {
  const name=normalize(product.name);
  if(!/^[a-z]+(?: [a-z]+)+$/.test(name)) continue;
  const compact=name.replaceAll(' ','');
  assert.ok(!completeNames.has(compact)||completeNames.get(compact)===name,`Ambiguous compact identity: ${compact}`);
  completeNames.set(compact,name);
  assert.equal(matches(product,compact),true,product.name);
  assert.equal(matches(product,`${product.name} ${product.volume_ml}ml`),true,product.name);
}
for(const q of ["Prada L'Homme EDT 100 ml",'Prada L’Homme EDT 100 ml','Prada L-Homme EDT 100 ml','Prada LHomme EDT 100 ml']) {
  assert.deepEqual(publicProducts.filter(p=>matches(p,q)).map(p=>p.product_id),['SC-PRADA-LHOMME-100'],q);
}
assert.deepEqual(publicProducts.filter(p=>matches(p,'Prada LHomme EDP 100 ml')).map(p=>p.product_id),[]);
for(const q of ['zzBlackOpium','BlackOpiumzz','BlackOpi','UnknownFragranceXYZ','BurberryGoddess','PradaParadoxe','GoodGirl','CocoMademoiselle','MonGuerlain','Widian London']) {
  assert.deepEqual(publicProducts.filter(p=>matches(p,q)).map(p=>p.product_id),[],q);
}
assert.equal(variant({brand:'Test',name:'Belle',concentration:'Eau de Parfum',volume_ml:100},'Belle Le Parfum'),false);
assert.equal(variant({brand:'Test',name:'Belle Le Parfum',concentration:'Eau de Parfum',volume_ml:100},'Belle Le Parfum'),true);
console.log(`Compact search: ${required.length} exact public variants; ${completeNames.size} unambiguous full names; size, flanker, refill and private-profile exclusions passed.`);

// This already-public profile and its purchase guide describe a refillable
// 90-ml bottle. A shopper using that distinction must reach the bottle, while
// refill packs, other concentrations and other sizes stay excluded.
const libreBottle=publicProducts.find(p=>p.product_id==='SC-YSL-LIBRE-EDP-90');
assert.ok(libreBottle);
const refillableBottleQueries=[
  'YSL Libre EDP 90 ml nachfüllbar',
  'YSL Libre nachfüllbarer Flakon 90 ml',
  'Yves Saint Laurent Libre refillable EDP 90ml',
  'LIBRE NACHFÜLLBAR 90 ML',
];
for(const q of refillableBottleQueries) {
  assert.deepEqual(publicProducts.filter(p=>matches(p,q)).map(p=>p.product_id),[libreBottle.product_id],q);
}
for(const q of [
  'YSL Libre Refill 100 ml', 'YSL Libre Refill 90 ml',
  'YSL Libre Nachfüllung 90 ml', 'YSL Libre nachfüllbar 100 ml',
  'YSL Libre nachfüllbar 50 ml', 'YSL Libre nachfüllbar EDT 90 ml',
  'YSL Libre Intense nachfüllbar 90 ml', 'YSL Libre Le Parfum nachfüllbar 90 ml',
]) assert.deepEqual(publicProducts.filter(p=>matches(p,q)).map(p=>p.product_id),[],q);
for(const changedIdentity of [
  {product_id:'UNKNOWN'}, {brand:'Other'}, {name:'Libre Intense'},
  {concentration:'Eau de Toilette'}, {volume_ml:100},
]) assert.equal(matches({...libreBottle,...changedIdentity},'nachfüllbar'),false,JSON.stringify(changedIdentity));
console.log('Libre buyer search: refillable 90-ml bottle found; refill packs, other sizes and flankers excluded.');
