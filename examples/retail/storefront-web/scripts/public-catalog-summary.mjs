import {readFileSync} from 'node:fs';
const read=name=>JSON.parse(readFileSync(new URL(`../lib/generated/${name}`,import.meta.url),'utf8'));
const sources=read('public-fragrances.json').products;
export const publicRows=[...read('public-catalog.json').products.filter(p=>p.product_id.startsWith('SC-')&&p.category==='fragrance'&&p.in_stock!==false&&!sources.find(f=>f.product_id===p.product_id)?.validation?.blockers?.some(b=>String(b).trim())),...read('released-profiles.json').profiles];
export const publicCount=publicRows.length;
